"""Hospital portal: staff of ONE hospital manage its beds and incoming patients.

Every route checks the caller's membership for the hospital in the URL.
hospital_staff can update beds and act on holds; hospital_admin can also
change bed totals, manage on-call contacts, colleagues and API keys.
"""

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection
from pydantic import BaseModel, Field

from ..auth import API_KEY_SCOPES, Staff, check_hospital_access, current_staff, generate_api_key
from ..db import audit, get_db
from ..ledger import HOLD_SELECT, expire_holds, get_hold_for_update, hold_view, transition_hold, update_ward, wards_for
from ..util import normalize_phone, pepper_hash

router = APIRouter(prefix="/v1", tags=["hospital"])

WardKind = Literal["ER", "ICU", "general", "maternity", "paediatric"]


# ---------------------------------------------------------------- joining the network


class WardInit(BaseModel):
    kind: WardKind
    total: int = Field(ge=0, le=5000)
    occupied: int = Field(0, ge=0)


class HospitalApplication(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    region: str
    district: str
    city: str
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    phone: Optional[str] = None
    license_number: str = Field(min_length=3, description="HeFRA facility licence number")
    wards: list[WardInit] = Field(min_length=1)


@router.post("/hospitals/apply", status_code=201)
def apply_to_join(body: HospitalApplication, staff: Staff = Depends(current_staff), db: Connection = Depends(get_db, scope="function")):
    """A signed-in staff member registers their hospital. It stays hidden from
    the public and cannot receive patients until a BedAlert admin verifies it.
    The applicant becomes the hospital's admin."""
    if len({w.kind for w in body.wards}) != len(body.wards):
        raise HTTPException(422, "Each ward kind can only be listed once")
    for w in body.wards:
        if w.occupied > w.total:
            raise HTTPException(422, f"{w.kind}: occupied cannot exceed total")
    h = db.execute(
        """insert into hospitals (name, region, district, city, lat, lng, phone, license_number)
           values (%s, %s, %s, %s, %s, %s, %s, %s) returning id::text, status""",
        (body.name, body.region, body.district, body.city, body.lat, body.lng,
         normalize_phone(body.phone) if body.phone else None, body.license_number),
    ).fetchone()
    for w in body.wards:
        db.execute(
            "insert into wards (hospital_id, kind, total, occupied, updated_by) values (%s, %s, %s, %s, %s)",
            (h["id"], w.kind, w.total, w.occupied, staff.actor),
        )
    db.execute(
        "insert into memberships (user_id, role, hospital_id) values (%s, 'hospital_admin', %s)", (staff.user_id, h["id"])
    )
    audit(db, staff.actor, "hospital.applied", "hospital", h["id"], name=body.name)
    return {"id": h["id"], "status": h["status"],
            "message": "Thanks. BedAlert will verify your licence before the hospital goes live."}


@router.get("/me")
def me(staff: Staff = Depends(current_staff), db: Connection = Depends(get_db, scope="function")):
    """Who am I and which hospitals / agencies can I act for? The portal and
    dispatch apps use this to decide what to show."""
    hospitals = db.execute(
        """select h.id::text, h.name, h.status, m.role from memberships m
           join hospitals h on h.id = m.hospital_id where m.user_id = %s order by h.name""",
        (staff.user_id,),
    ).fetchall()
    agencies = db.execute(
        """select a.id::text, a.name, a.region from memberships m
           join agencies a on a.id = m.agency_id where m.user_id = %s order by a.name""",
        (staff.user_id,),
    ).fetchall()
    return {"user_id": staff.user_id, "email": staff.email, "network_admin": staff.is_network_admin,
            "hospitals": hospitals, "agencies": agencies}


# ---------------------------------------------------------------- dashboard + beds


@router.get("/hospital/{hospital_id}")
def hospital_dashboard(hospital_id: str, staff: Staff = Depends(current_staff), db: Connection = Depends(get_db, scope="function")):
    role = check_hospital_access(staff, hospital_id)
    expire_holds(db)
    h = db.execute(
        "select id::text, name, region, district, city, lat, lng, phone, license_number, status from hospitals where id = %s",
        (hospital_id,),
    ).fetchone()
    if not h:
        raise HTTPException(404, "Hospital not found")
    contacts = db.execute(
        "select id::text, name, role, phone, on_call from on_call_contacts where hospital_id = %s order by name",
        (hospital_id,),
    ).fetchall()
    return {**h, "your_role": role, "wards": wards_for(db, [hospital_id]).get(hospital_id, []), "on_call": contacts}


class WardUpdate(BaseModel):
    occupied: Optional[int] = Field(None, ge=0)
    free: Optional[int] = Field(None, ge=0, description="Physically empty beds right now")
    free_delta: Optional[int] = Field(None, description="+1 when a bed frees up, -1 when one is taken")
    total: Optional[int] = Field(None, ge=0, le=5000, description="Admins only")


@router.put("/hospital/{hospital_id}/wards/{kind}")
def set_ward(hospital_id: str, kind: WardKind, body: WardUpdate,
             staff: Staff = Depends(current_staff), db: Connection = Depends(get_db, scope="function")):
    check_hospital_access(staff, hospital_id, admin=body.total is not None)
    return update_ward(db, hospital_id=hospital_id, kind=kind, actor=staff.actor, **body.model_dump())


# ---------------------------------------------------------------- incoming patients


@router.get("/hospital/{hospital_id}/holds")
def incoming(hospital_id: str, status: Literal["active", "all"] = "active",
             staff: Staff = Depends(current_staff), db: Connection = Depends(get_db, scope="function")):
    check_hospital_access(staff, hospital_id)
    expire_holds(db)
    where = "x.hospital_id = %s" + (" and x.status in ('held', 'accepted')" if status == "active" else "")
    rows = db.execute(HOLD_SELECT + f" where {where} order by x.created_at desc limit 200", (hospital_id,)).fetchall()
    return [hold_view(r, include_private=True) for r in rows]


class HoldAction(BaseModel):
    reason: Optional[str] = Field(None, max_length=200)


@router.post("/hospital/{hospital_id}/holds/{hold_id}/{action}")
def act_on_hold(hospital_id: str, hold_id: str, action: Literal["accept", "decline", "arrive"],
                body: HoldAction = HoldAction(),
                staff: Staff = Depends(current_staff), db: Connection = Depends(get_db, scope="function")):
    check_hospital_access(staff, hospital_id)
    hold = get_hold_for_update(db, hold_id)
    if str(hold["hospital_id"]) != hospital_id:
        raise HTTPException(404, "Hold not found")
    return transition_hold(db, hold, action, actor=staff.actor, reason=body.reason)


# ---------------------------------------------------------------- on-call contacts (admin)


class Contact(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    role: str = "doctor"
    phone: str
    on_call: bool = True


@router.put("/hospital/{hospital_id}/on-call")
def replace_on_call(hospital_id: str, contacts: list[Contact],
                    staff: Staff = Depends(current_staff), db: Connection = Depends(get_db, scope="function")):
    """Replace the list of people texted when a patient is on the way."""
    check_hospital_access(staff, hospital_id, admin=True)
    db.execute("delete from on_call_contacts where hospital_id = %s", (hospital_id,))
    for c in contacts:
        db.execute(
            "insert into on_call_contacts (hospital_id, name, role, phone, on_call) values (%s, %s, %s, %s, %s)",
            (hospital_id, c.name, c.role, normalize_phone(c.phone), c.on_call),
        )
    audit(db, staff.actor, "on_call.replaced", "hospital", hospital_id, count=len(contacts))
    return db.execute(
        "select id::text, name, role, phone, on_call from on_call_contacts where hospital_id = %s order by name",
        (hospital_id,),
    ).fetchall()


# ---------------------------------------------------------------- colleagues (admin)


class MemberAdd(BaseModel):
    email: str
    role: Literal["hospital_admin", "hospital_staff"] = "hospital_staff"


@router.post("/hospital/{hospital_id}/members", status_code=201)
def add_member(hospital_id: str, body: MemberAdd, staff: Staff = Depends(current_staff), db: Connection = Depends(get_db, scope="function")):
    check_hospital_access(staff, hospital_id, admin=True)
    user = db.execute("select user_id::text from staff where lower(email) = lower(%s)", (body.email,)).fetchone()
    if not user:
        raise HTTPException(404, "No BedAlert account with that email. Ask them to sign up and sign in once first.")
    db.execute(
        "insert into memberships (user_id, role, hospital_id) values (%s, %s, %s) on conflict do nothing",
        (user["user_id"], body.role, hospital_id),
    )
    audit(db, staff.actor, "membership.added", "hospital", hospital_id, user_id=user["user_id"], role=body.role)
    return {"user_id": user["user_id"], "role": body.role}


@router.get("/hospital/{hospital_id}/members")
def list_members(hospital_id: str, staff: Staff = Depends(current_staff), db: Connection = Depends(get_db, scope="function")):
    check_hospital_access(staff, hospital_id, admin=True)
    return db.execute(
        """select s.user_id::text, s.email, s.full_name, m.role from memberships m
           join staff s on s.user_id = m.user_id where m.hospital_id = %s order by s.email""",
        (hospital_id,),
    ).fetchall()


# ---------------------------------------------------------------- API keys (admin)


class ApiKeyCreate(BaseModel):
    label: str = Field(min_length=2, max_length=80, description="e.g. 'Lightwave HIS production'")
    scopes: list[Literal["beds:write", "holds:read", "holds:write"]] = list(API_KEY_SCOPES)


@router.post("/hospital/{hospital_id}/api-keys", status_code=201)
def create_api_key(hospital_id: str, body: ApiKeyCreate,
                   staff: Staff = Depends(current_staff), db: Connection = Depends(get_db, scope="function")):
    check_hospital_access(staff, hospital_id, admin=True)
    status = db.execute("select status from hospitals where id = %s", (hospital_id,)).fetchone()
    if not status or status["status"] != "verified":
        raise HTTPException(409, "API keys are available once the hospital is verified")
    key, prefix = generate_api_key()
    row = db.execute(
        """insert into api_keys (hospital_id, label, prefix, key_hash, scopes, created_by)
           values (%s, %s, %s, %s, %s, %s) returning id::text, created_at""",
        (hospital_id, body.label, prefix, pepper_hash(key), sorted(set(body.scopes)), staff.user_id),
    ).fetchone()
    audit(db, staff.actor, "api_key.created", "api_key", row["id"], hospital_id=hospital_id, prefix=prefix)
    return {"id": row["id"], "label": body.label, "prefix": prefix, "scopes": sorted(set(body.scopes)),
            "key": key, "warning": "Copy this key now. BedAlert does not store it and cannot show it again."}


@router.get("/hospital/{hospital_id}/api-keys")
def list_api_keys(hospital_id: str, staff: Staff = Depends(current_staff), db: Connection = Depends(get_db, scope="function")):
    check_hospital_access(staff, hospital_id, admin=True)
    return db.execute(
        """select id::text, label, prefix, scopes, created_at, last_used_at, revoked_at
           from api_keys where hospital_id = %s order by created_at desc""",
        (hospital_id,),
    ).fetchall()


@router.delete("/hospital/{hospital_id}/api-keys/{key_id}")
def revoke_api_key(hospital_id: str, key_id: str, staff: Staff = Depends(current_staff), db: Connection = Depends(get_db, scope="function")):
    check_hospital_access(staff, hospital_id, admin=True)
    row = db.execute(
        "update api_keys set revoked_at = now() where id = %s and hospital_id = %s and revoked_at is null returning id",
        (key_id, hospital_id),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Active key not found")
    audit(db, staff.actor, "api_key.revoked", "api_key", key_id, hospital_id=hospital_id)
    return {"revoked": True}

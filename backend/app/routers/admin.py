"""BedAlert network admin: verify hospitals, create dispatch agencies, grant roles."""

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection
from pydantic import BaseModel

from ..auth import Staff, require_network_admin
from ..db import audit, get_db

router = APIRouter(prefix="/v1/admin", tags=["network admin"])


@router.get("/hospitals")
def hospitals(status: Optional[Literal["pending", "verified", "suspended"]] = None,
              staff: Staff = Depends(require_network_admin), db: Connection = Depends(get_db, scope="function")):
    sql = "select id::text, name, region, district, city, phone, license_number, status, created_at, verified_at from hospitals"
    params: tuple = ()
    if status:
        sql += " where status = %s"
        params = (status,)
    return db.execute(sql + " order by created_at desc", params).fetchall()


@router.post("/hospitals/{hospital_id}/{action}")
def set_status(hospital_id: str, action: Literal["verify", "suspend"],
               staff: Staff = Depends(require_network_admin), db: Connection = Depends(get_db, scope="function")):
    """Verify only after checking the HeFRA licence and speaking to the facility."""
    new_status = "verified" if action == "verify" else "suspended"
    row = db.execute(
        """update hospitals set status = %s,
               verified_at = case when %s = 'verified' then now() else verified_at end,
               verified_by = case when %s = 'verified' then %s::uuid else verified_by end
           where id = %s returning id::text, name, status""",
        (new_status, new_status, new_status, staff.user_id, hospital_id),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Hospital not found")
    audit(db, staff.actor, f"hospital.{new_status}", "hospital", hospital_id)
    return row


class AgencyCreate(BaseModel):
    name: str
    region: Optional[str] = None


@router.post("/agencies", status_code=201)
def create_agency(body: AgencyCreate, staff: Staff = Depends(require_network_admin), db: Connection = Depends(get_db, scope="function")):
    row = db.execute(
        "insert into agencies (name, region) values (%s, %s) returning id::text, name, region", (body.name, body.region)
    ).fetchone()
    audit(db, staff.actor, "agency.created", "agency", row["id"], name=body.name)
    return row


@router.get("/agencies")
def list_agencies(staff: Staff = Depends(require_network_admin), db: Connection = Depends(get_db, scope="function")):
    return db.execute("select id::text, name, region, created_at from agencies order by name").fetchall()


class Grant(BaseModel):
    email: str
    role: Literal["network_admin", "hospital_admin", "hospital_staff", "dispatcher"]
    hospital_id: Optional[str] = None
    agency_id: Optional[str] = None


@router.post("/memberships", status_code=201)
def grant(body: Grant, staff: Staff = Depends(require_network_admin), db: Connection = Depends(get_db, scope="function")):
    user = db.execute("select user_id::text from staff where lower(email) = lower(%s)", (body.email,)).fetchone()
    if not user:
        raise HTTPException(404, "No BedAlert account with that email. Ask them to sign in once first.")
    hospital_id = body.hospital_id if body.role in ("hospital_admin", "hospital_staff") else None
    agency_id = body.agency_id if body.role == "dispatcher" else None
    if body.role in ("hospital_admin", "hospital_staff") and not hospital_id:
        raise HTTPException(422, "hospital_id is required for hospital roles")
    if body.role == "dispatcher" and not agency_id:
        raise HTTPException(422, "agency_id is required for dispatchers")
    db.execute(
        "insert into memberships (user_id, role, hospital_id, agency_id) values (%s, %s, %s, %s) on conflict do nothing",
        (user["user_id"], body.role, hospital_id, agency_id),
    )
    audit(db, staff.actor, "membership.granted", "staff", user["user_id"], role=body.role,
          hospital_id=hospital_id, agency_id=agency_id)
    return {"user_id": user["user_id"], "role": body.role, "hospital_id": hospital_id, "agency_id": agency_id}


@router.get("/data-quality")
def data_quality(staff: Staff = Depends(require_network_admin), db: Connection = Depends(get_db, scope="function")):
    """Verified hospitals whose numbers are going stale — call them."""
    return db.execute(
        """select h.id::text, h.name, h.phone, min(w.updated_at) as oldest_update,
                  (extract(epoch from now() - max(w.updated_at)) / 60)::int as minutes_since_last_update
           from hospitals h join wards w on w.hospital_id = h.id
           where h.status = 'verified'
           group by h.id order by max(w.updated_at)"""
    ).fetchall()

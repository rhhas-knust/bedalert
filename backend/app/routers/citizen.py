"""Citizens: verify a phone number by SMS code, then hold one bed at a time."""

from datetime import timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection
from pydantic import BaseModel, Field

from ..auth import Citizen, current_citizen, issue_citizen_token
from ..config import settings
from ..db import audit, get_db
from ..ledger import HOLD_SELECT, create_hold, get_hold_for_update, hold_view, transition_hold
from ..sms import queue_sms
from ..util import normalize_phone, pepper_hash, utcnow

router = APIRouter(prefix="/v1", tags=["citizen"])

OTP_TTL = timedelta(minutes=5)
OTP_MAX_PER_10_MIN = 3
OTP_MAX_ATTEMPTS = 5


class OtpRequest(BaseModel):
    phone: str


class OtpVerify(BaseModel):
    phone: str
    code: str = Field(min_length=6, max_length=6)


@router.post("/auth/otp/request")
def request_otp(body: OtpRequest, db: Connection = Depends(get_db, scope="function")):
    import secrets

    phone = normalize_phone(body.phone)
    recent = db.execute(
        "select count(*) as n from otp_codes where phone = %s and created_at > now() - interval '10 minutes'",
        (phone,),
    ).fetchone()["n"]
    if recent >= OTP_MAX_PER_10_MIN:
        raise HTTPException(429, "Too many codes requested. Wait a few minutes and try again.")
    code = f"{secrets.randbelow(10**6):06d}"
    db.execute(
        "insert into otp_codes (phone, code_hash, expires_at) values (%s, %s, %s)",
        (phone, pepper_hash(f"{phone}:{code}"), utcnow() + OTP_TTL),
    )
    queue_sms(db, phone, f"Your BedAlert code is {code}. It expires in 5 minutes.", "otp")
    response = {"phone": phone, "expires_in": int(OTP_TTL.total_seconds())}
    if settings.is_dev:
        response["dev_code"] = code  # local development only — never returned in production
    return response


@router.post("/auth/otp/verify")
def verify_otp(body: OtpVerify, db: Connection = Depends(get_db, scope="function")):
    phone = normalize_phone(body.phone)
    row = db.execute(
        """select id, code_hash, attempts from otp_codes
           where phone = %s and consumed_at is null and expires_at > now()
           order by created_at desc limit 1 for update""",
        (phone,),
    ).fetchone()
    if not row or row["attempts"] >= OTP_MAX_ATTEMPTS:
        raise HTTPException(400, "Code expired. Request a new one.")
    if row["code_hash"] != pepper_hash(f"{phone}:{body.code}"):
        db.execute("update otp_codes set attempts = attempts + 1 where id = %s", (row["id"],))
        # Commit the attempt count even though we return an error.
        db.commit()
        raise HTTPException(400, "Wrong code")
    db.execute("update otp_codes set consumed_at = now() where id = %s", (row["id"],))
    token, expires_in = issue_citizen_token(phone)
    return {"access_token": token, "token_type": "bearer", "expires_in": expires_in, "phone": phone}


class CitizenHoldRequest(BaseModel):
    hospital_id: str
    type: Literal["emergency", "stable"]
    ward: Optional[Literal["ER", "ICU", "general", "maternity", "paediatric"]] = None
    condition_category: str
    condition_note: Optional[str] = Field(None, max_length=280)
    age_group: Optional[Literal["0-17", "18-39", "40-64", "65+"]] = None
    sex: Optional[Literal["female", "male", "unspecified"]] = None


@router.post("/holds", status_code=201)
def hold_bed(body: CitizenHoldRequest,
             citizen: Citizen = Depends(current_citizen), db: Connection = Depends(get_db, scope="function")):
    ward = body.ward or ("ER" if body.type == "emergency" else "general")
    if body.type == "stable" and ward in ("ER", "ICU"):
        raise HTTPException(422, "ER and ICU beds are for emergencies")
    hold = create_hold(
        db,
        actor=citizen.actor,
        hospital_id=body.hospital_id,
        ward=ward,
        source="public",
        severity="severe" if body.type == "emergency" else "stable",
        condition_category=body.condition_category,
        condition_note=body.condition_note,
        age_group=body.age_group,
        sex=body.sex,
        citizen_phone=citizen.phone,
    )
    return hold


@router.get("/holds/mine")
def my_holds(citizen: Citizen = Depends(current_citizen), db: Connection = Depends(get_db, scope="function")):
    rows = db.execute(
        HOLD_SELECT + " where x.citizen_phone = %s order by x.created_at desc limit 20", (citizen.phone,)
    ).fetchall()
    return [hold_view(r) for r in rows]


@router.post("/holds/{hold_id}/cancel")
def cancel_my_hold(hold_id: str, citizen: Citizen = Depends(current_citizen), db: Connection = Depends(get_db, scope="function")):
    hold = get_hold_for_update(db, hold_id)
    if hold["citizen_phone"] != citizen.phone:
        raise HTTPException(404, "Hold not found")
    result = transition_hold(db, hold, "cancel", actor=citizen.actor)
    audit(db, citizen.actor, "hold.cancelled_by_citizen", "hold", hold_id)
    return hold_view({**hold, "status": result["hold"]["status"]})

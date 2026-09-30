"""Dispatch console: ambulance controllers find and hold the best bed."""

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg import Connection
from pydantic import BaseModel, Field

from ..auth import Staff, require_dispatcher
from ..db import get_db
from ..ledger import HOLD_SELECT, create_hold, expire_holds, get_hold_for_update, hold_view, rank_candidates, transition_hold

router = APIRouter(prefix="/v1/dispatch", tags=["dispatch"])

Severity = Literal["critical", "severe", "moderate"]
WardKind = Literal["ER", "ICU", "general", "maternity", "paediatric"]


def _ward_for(severity: str, ward: str) -> str:
    # Critical cases always go to Emergency whatever was picked.
    return "ER" if severity == "critical" else ward


def _agency(staff: Staff, agency_id: Optional[str]) -> str:
    agencies = staff.agency_ids()
    if agency_id is None:
        return agencies[0]
    if agency_id not in agencies:
        raise HTTPException(403, "You are not a dispatcher for that agency")
    return agency_id


@router.get("/options")
def options(lat: float = Query(ge=-90, le=90), lng: float = Query(ge=-180, le=180),
            severity: Severity = "severe", ward: WardKind = "ER",
            staff: Staff = Depends(require_dispatcher), db: Connection = Depends(get_db, scope="function")):
    """Ranked hospitals that can take this patient now (no bed is held)."""
    return rank_candidates(db, lat=lat, lng=lng, ward=_ward_for(severity, ward))[:10]


class DispatchRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    severity: Severity
    ward: WardKind = "ER"
    condition_category: str
    condition_note: Optional[str] = Field(None, max_length=280)
    age_group: Optional[Literal["0-17", "18-39", "40-64", "65+"]] = None
    sex: Optional[Literal["female", "male", "unspecified"]] = None
    hospital_id: Optional[str] = Field(None, description="Pick a specific hospital; default is the best-ranked one")
    agency_id: Optional[str] = None


@router.post("/holds", status_code=201)
def dispatch(body: DispatchRequest, staff: Staff = Depends(require_dispatcher), db: Connection = Depends(get_db, scope="function")):
    ward = _ward_for(body.severity, body.ward)
    agency_id = _agency(staff, body.agency_id)
    candidates = rank_candidates(db, lat=body.lat, lng=body.lng, ward=ward)
    if body.hospital_id:
        candidates = [c for c in candidates if c["hospital_id"] == body.hospital_id]
    if not candidates:
        raise HTTPException(409, f"No hospital has a free {ward} bed right now")
    last_error = None
    for c in candidates[:5]:
        try:
            with db.transaction():
                hold = create_hold(
                    db,
                    actor=staff.actor,
                    hospital_id=c["hospital_id"],
                    ward=ward,
                    source="dispatcher",
                    severity=body.severity,
                    condition_category=body.condition_category,
                    condition_note=body.condition_note,
                    age_group=body.age_group,
                    sex=body.sex,
                    dispatcher_user_id=staff.user_id,
                    agency_id=agency_id,
                    origin=(body.lat, body.lng),
                    eta=c["eta_minutes"],
                )
            return {**hold, "distance_km": c["distance_km"], "data_fresh": c["fresh"]}
        except HTTPException as exc:
            if exc.status_code != 409:
                raise
            last_error = exc  # taken in the last second — try the next hospital
    raise last_error


@router.get("/holds")
def agency_holds(status: Literal["active", "all"] = "active",
                 staff: Staff = Depends(require_dispatcher), db: Connection = Depends(get_db, scope="function")):
    """Live board for this dispatcher's agencies. Follow `previous_hold_id`
    to see re-routes after a hospital declined."""
    expire_holds(db)
    where = "x.agency_id = any(%s::uuid[])" + (" and x.status in ('held', 'accepted')" if status == "active" else "")
    rows = db.execute(HOLD_SELECT + f" where {where} order by x.created_at desc limit 200", (staff.agency_ids(),)).fetchall()
    return [hold_view(r, include_private=True) for r in rows]


@router.post("/holds/{hold_id}/cancel")
def cancel(hold_id: str, staff: Staff = Depends(require_dispatcher), db: Connection = Depends(get_db, scope="function")):
    hold = get_hold_for_update(db, hold_id)
    if str(hold["agency_id"]) not in staff.agency_ids():
        raise HTTPException(404, "Hold not found")
    return transition_hold(db, hold, "cancel", actor=staff.actor)

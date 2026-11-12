"""Open to anyone, no login: find beds. Returns counts only — never patients."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg import Connection

from ..db import get_db
from ..ledger import CONDITION_CATEGORIES, WARD_KINDS, public_facilities

router = APIRouter(prefix="/v1", tags=["public"])


@router.get("/facilities")
def list_facilities(
    region: Optional[str] = None,
    ward: Optional[str] = Query(None, description="Only hospitals with this ward: " + ", ".join(WARD_KINDS)),
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lng: Optional[float] = Query(None, ge=-180, le=180),
    db: Connection = Depends(get_db, scope="function"),
):
    """Verified hospitals with free beds per ward and how fresh each number is.
    Pass lat/lng to sort by distance."""
    return public_facilities(db, region=region, ward=ward, lat=lat, lng=lng)


@router.get("/facilities/{hospital_id}")
def get_facility(hospital_id: str, db: Connection = Depends(get_db, scope="function")):
    try:
        found = public_facilities(db, hospital_id=hospital_id)
    except Exception:  # malformed uuid
        found = []
    if not found:
        raise HTTPException(404, "Hospital not found")
    return found[0]


@router.get("/regions")
def list_regions(db: Connection = Depends(get_db, scope="function")):
    rows = db.execute(
        "select region, count(*)::int as hospitals from hospitals where status = 'verified' group by region order by region"
    ).fetchall()
    return rows


@router.get("/meta")
def meta():
    """Picklists shared by every app."""
    return {
        "wards": WARD_KINDS,
        "condition_categories": [{"id": k, "label": v} for k, v in CONDITION_CATEGORIES.items()],
        "age_groups": ["0-17", "18-39", "40-64", "65+"],
        "sex": ["female", "male", "unspecified"],
        "emergency_number": "112",
    }

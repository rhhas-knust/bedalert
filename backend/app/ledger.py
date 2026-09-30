"""The bed ledger: availability, holds, and routing.

Everything that changes bed numbers goes through here, inside the caller's
transaction, with the ward row locked (SELECT ... FOR UPDATE). That is what
stops two people from getting the last bed.

Hold lifecycle:

    held ──► accepted ──► arrived
      │         │
      ├─────────┴──► declined   (dispatcher holds are re-routed automatically)
      ├─────────┴──► cancelled  (by the citizen / dispatcher)
      └─────────┴──► expired    (patient did not arrive in time; bed released)
"""

from datetime import timedelta
from typing import Optional

from fastapi import HTTPException
from psycopg import Connection, errors

from .config import settings
from .db import audit
from .sms import queue_sms
from .util import eta_minutes, haversine_km, new_code, utcnow

WARD_KINDS = ("ER", "ICU", "general", "maternity", "paediatric")
URGENT_WARDS = ("ER", "ICU", "maternity")
ACTIVE = ("held", "accepted")

CONDITION_CATEGORIES = {
    "chest_pain": "Chest pain",
    "road_accident": "Road accident",
    "labour": "Labour / pregnancy",
    "breathing_difficulty": "Breathing difficulty",
    "stroke_signs": "Stroke signs",
    "bleeding_injury": "Bleeding / injury",
    "burns": "Burns",
    "poisoning": "Poisoning",
    "child_fever": "Child with high fever",
    "referral": "Referral / check-up",
    "other": "Other",
}

_WARDS_SQL = """
    select w.id::text, w.hospital_id::text, w.kind, w.total, w.occupied, w.updated_at,
           (select count(*) from holds x where x.ward_id = w.id and x.status in ('held', 'accepted'))::int as held
    from wards w
"""


# ---------------------------------------------------------------- availability


def expire_holds(conn: Connection) -> int:
    """Release every hold whose window has passed. Cheap; called before any
    read or write of availability so numbers are always current."""
    rows = conn.execute(
        """update holds set status = 'expired', closed_at = now()
           where status in ('held', 'accepted') and expires_at < now()
           returning id::text, code"""
    ).fetchall()
    for r in rows:
        audit(conn, "system", "hold.expired", "hold", r["id"], code=r["code"])
    return len(rows)


def _ward_view(w: dict) -> dict:
    minutes = int((utcnow() - w["updated_at"]).total_seconds() // 60)
    return {
        "kind": w["kind"],
        "total": w["total"],
        "available": max(0, w["total"] - w["occupied"] - w["held"]),
        "updated_at": w["updated_at"].isoformat(),
        "updated_minutes_ago": minutes,
        "fresh": minutes <= settings.stale_after_minutes,
    }


def wards_for(conn: Connection, hospital_ids: list) -> dict:
    """{hospital_id: [ward view, ...]}"""
    if not hospital_ids:
        return {}
    rows = conn.execute(_WARDS_SQL + " where w.hospital_id = any(%s::uuid[]) order by w.kind", (hospital_ids,)).fetchall()
    out: dict = {}
    for w in rows:
        out.setdefault(w["hospital_id"], []).append({**_ward_view(w), "occupied": w["occupied"], "held": w["held"]})
    return out


def public_facilities(conn: Connection, *, region=None, ward=None, lat=None, lng=None, hospital_id=None) -> list:
    """What anyone may see: verified hospitals, their free beds and how fresh
    those numbers are. No patients, no staff names."""
    expire_holds(conn)
    clauses, params = ["status = 'verified'"], []
    if region:
        clauses.append("region = %s")
        params.append(region)
    if hospital_id:
        clauses.append("id = %s")
        params.append(hospital_id)
    hospitals = conn.execute(
        "select id::text, name, region, district, city, lat, lng, phone from hospitals where "
        + " and ".join(clauses) + " order by name",
        params,
    ).fetchall()
    ward_map = wards_for(conn, [h["id"] for h in hospitals])
    result = []
    for h in hospitals:
        wards = [
            {k: v for k, v in w.items() if k not in ("occupied", "held")}
            for w in ward_map.get(h["id"], [])
        ]
        if ward:
            wards = [w for w in wards if w["kind"] == ward]
            if not wards:
                continue
        item = {**h, "wards": wards}
        if lat is not None and lng is not None:
            item["distance_km"] = round(haversine_km(lat, lng, h["lat"], h["lng"]), 1)
        result.append(item)
    if lat is not None and lng is not None:
        result.sort(key=lambda x: x["distance_km"])
    return result


def rank_candidates(conn: Connection, *, lat: float, lng: float, ward: str, exclude: tuple = ()) -> list:
    """Hospitals that can take a patient now, best first: hospitals with
    fresh numbers before stale ones, then nearest."""
    candidates = []
    for f in public_facilities(conn, ward=ward, lat=lat, lng=lng):
        if f["id"] in exclude:
            continue
        w = f["wards"][0]
        if w["available"] <= 0:
            continue
        candidates.append({
            "hospital_id": f["id"],
            "hospital_name": f["name"],
            "hospital_phone": f["phone"],
            "city": f["city"],
            "ward": ward,
            "available": w["available"],
            "fresh": w["fresh"],
            "updated_minutes_ago": w["updated_minutes_ago"],
            "distance_km": f["distance_km"],
            "eta_minutes": eta_minutes(f["distance_km"]),
        })
    candidates.sort(key=lambda c: (not c["fresh"], c["distance_km"]))
    return candidates


# ---------------------------------------------------------------- holds


def _hold_window(ward: str, severity: str, eta: Optional[int]) -> timedelta:
    urgent = ward in URGENT_WARDS or severity != "stable"
    minutes = settings.hold_minutes_emergency if urgent else settings.hold_minutes_ward
    if eta:
        minutes = max(minutes, eta + 20)
    return timedelta(minutes=minutes)


def create_hold(
    conn: Connection,
    *,
    actor: str,
    hospital_id: str,
    ward: str,
    source: str,
    severity: str,
    condition_category: str,
    condition_note: Optional[str] = None,
    age_group: Optional[str] = None,
    sex: Optional[str] = None,
    citizen_phone: Optional[str] = None,
    dispatcher_user_id: Optional[str] = None,
    agency_id: Optional[str] = None,
    origin: Optional[tuple] = None,
    eta: Optional[int] = None,
    route_chain_id: Optional[str] = None,
    previous_hold_id: Optional[str] = None,
) -> dict:
    if ward not in WARD_KINDS:
        raise HTTPException(422, f"Unknown ward '{ward}'")
    if condition_category not in CONDITION_CATEGORIES:
        raise HTTPException(422, f"Unknown condition category '{condition_category}'")
    expire_holds(conn)

    w = conn.execute(
        """select w.id::text, w.total, w.occupied, h.name as hospital_name, h.phone as hospital_phone
           from wards w join hospitals h on h.id = w.hospital_id
           where h.id = %s and w.kind = %s and h.status = 'verified'
           for update of w""",
        (hospital_id, ward),
    ).fetchone()
    if not w:
        raise HTTPException(404, f"This hospital is not taking {ward} patients through BedAlert")
    held = conn.execute(
        "select count(*) as n from holds where ward_id = %s and status in ('held', 'accepted')", (w["id"],)
    ).fetchone()["n"]
    if w["total"] - w["occupied"] - held <= 0:
        raise HTTPException(409, f"No {ward} beds free at {w['hospital_name']} right now")

    expires_at = utcnow() + _hold_window(ward, severity, eta)
    for _ in range(5):
        code = new_code()
        try:
            with conn.transaction():  # savepoint, so a collision doesn't abort the request
                hold = conn.execute(
                    """insert into holds (code, hospital_id, ward_id, source, severity, condition_category,
                           condition_note, age_group, sex, citizen_phone, dispatcher_user_id, agency_id,
                           origin_lat, origin_lng, eta_minutes, route_chain_id, previous_hold_id, expires_at)
                       values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       returning *""",
                    (code, hospital_id, w["id"], source, severity, condition_category, condition_note,
                     age_group, sex, citizen_phone, dispatcher_user_id, agency_id,
                     origin[0] if origin else None, origin[1] if origin else None, eta,
                     route_chain_id, previous_hold_id, expires_at),
                ).fetchone()
            break
        except errors.UniqueViolation as exc:
            if exc.diag.constraint_name == "holds_one_active_per_phone_idx":
                raise HTTPException(409, "You already have an active bed hold. Cancel it before holding another.") from exc
            continue  # code collision — try another code
    else:
        raise HTTPException(500, "Could not allocate a hold code")

    if route_chain_id is None:
        conn.execute("update holds set route_chain_id = id where id = %s", (hold["id"],))
        hold["route_chain_id"] = hold["id"]

    audit(conn, actor, "hold.created", "hold", hold["id"], code=code, hospital_id=hospital_id, ward=ward, source=source)
    _notify_hospital(conn, hospital_id, hold, w["hospital_name"])
    if citizen_phone:
        queue_sms(
            conn, citizen_phone,
            f"BedAlert: {ward} bed held at {w['hospital_name']}. Code {code}. "
            f"Go now - hold ends {expires_at:%H:%M} UTC."
            + (f" Hospital: {w['hospital_phone']}." if w["hospital_phone"] else "")
            + " Emergency? Also call 112.",
            "hold_citizen",
        )
    return hold_view(hold, hospital_name=w["hospital_name"], hospital_phone=w["hospital_phone"], ward=ward)


def _notify_hospital(conn: Connection, hospital_id: str, hold: dict, hospital_name: str) -> None:
    contacts = conn.execute(
        "select phone from on_call_contacts where hospital_id = %s and on_call", (hospital_id,)
    ).fetchall()
    ward = conn.execute("select kind from wards where id = %s", (hold["ward_id"],)).fetchone()["kind"]
    eta = f", ETA ~{hold['eta_minutes']} min" if hold.get("eta_minutes") else ""
    body = (
        f"BedAlert {hospital_name}: incoming {hold['severity']} patient "
        f"({CONDITION_CATEGORIES[hold['condition_category']]}) for {ward}{eta}. "
        f"Code {hold['code']}. Please accept in the BedAlert portal."
    )
    for c in contacts:
        queue_sms(conn, c["phone"], body, "hold_hospital")


def hold_view(h: dict, *, hospital_name=None, hospital_phone=None, ward=None, include_private=False) -> dict:
    out = {
        "id": str(h["id"]),
        "code": h["code"],
        "hospital_id": str(h["hospital_id"]),
        "hospital_name": hospital_name or h.get("hospital_name"),
        "hospital_phone": hospital_phone or h.get("hospital_phone"),
        "ward": ward or h.get("ward"),
        "source": h["source"],
        "status": h["status"],
        "severity": h["severity"],
        "condition_category": h["condition_category"],
        "eta_minutes": h["eta_minutes"],
        "expires_at": h["expires_at"].isoformat(),
        "created_at": h["created_at"].isoformat(),
        "accepted_at": h["accepted_at"].isoformat() if h.get("accepted_at") else None,
        "arrived_at": h["arrived_at"].isoformat() if h.get("arrived_at") else None,
        "previous_hold_id": str(h["previous_hold_id"]) if h.get("previous_hold_id") else None,
    }
    if include_private:
        out.update({
            "condition_note": h["condition_note"],
            "age_group": h["age_group"],
            "sex": h["sex"],
            "citizen_phone": h["citizen_phone"],
            "decline_reason": h["decline_reason"],
        })
    return out


HOLD_SELECT = """
    select x.*, h.name as hospital_name, h.phone as hospital_phone, w.kind as ward
    from holds x join hospitals h on h.id = x.hospital_id join wards w on w.id = x.ward_id
"""


def get_hold_for_update(conn: Connection, hold_id: str) -> dict:
    expire_holds(conn)
    try:
        row = conn.execute(HOLD_SELECT + " where x.id = %s for update of x", (hold_id,)).fetchone()
    except errors.InvalidTextRepresentation:
        row = None
    if not row:
        raise HTTPException(404, "Hold not found")
    return row


_TRANSITIONS = {
    "accept": ({"held"}, "accepted"),
    "decline": ({"held", "accepted"}, "declined"),
    "arrive": ({"held", "accepted"}, "arrived"),
    "cancel": ({"held", "accepted"}, "cancelled"),
}


def transition_hold(conn: Connection, hold: dict, action: str, *, actor: str, reason: Optional[str] = None) -> dict:
    """Apply a lifecycle action to a hold locked with get_hold_for_update.
    Returns {"hold": ..., "rerouted_to": hold | None}."""
    allowed, new_status = _TRANSITIONS[action]
    if hold["status"] not in allowed:
        raise HTTPException(409, f"Cannot {action} a hold that is {hold['status']}")

    stamp = {"accept": "accepted_at", "arrive": "arrived_at"}.get(action)
    closes = new_status in ("arrived", "declined", "cancelled")
    sets = ["status = %s"]
    params: list = [new_status]
    if stamp:
        sets.append(f"{stamp} = now()")
    if closes:
        sets.append("closed_at = now()")
    if action == "decline":
        sets.append("decline_reason = %s")
        params.append(reason)
    updated = conn.execute(
        f"update holds set {', '.join(sets)} where id = %s returning *", (*params, hold["id"])
    ).fetchone()
    updated = {**updated, "hospital_name": hold["hospital_name"], "hospital_phone": hold["hospital_phone"], "ward": hold["ward"]}

    if action == "arrive":
        # The patient is now physically in a bed.
        conn.execute(
            "update wards set occupied = least(total, occupied + 1), updated_at = now(), updated_by = %s where id = %s",
            (actor, hold["ward_id"]),
        )
    audit(conn, actor, f"hold.{new_status}", "hold", hold["id"], code=hold["code"], reason=reason)

    rerouted = None
    if action == "decline":
        rerouted = _reroute(conn, updated, actor=actor)
        if hold["citizen_phone"]:
            queue_sms(
                conn, hold["citizen_phone"],
                f"BedAlert: {hold['hospital_name']} cannot take you (code {hold['code']}). "
                "Please choose another hospital on BedAlert or dial the BedAlert code again. Emergency? Call 112.",
                "hold_declined",
            )
    return {"hold": hold_view(updated, include_private=True), "rerouted_to": rerouted}


def _reroute(conn: Connection, declined: dict, *, actor: str) -> Optional[dict]:
    """Dispatcher holds follow the ambulance: when a hospital declines, hold a
    bed at the next best hospital straight away."""
    if declined["source"] != "dispatcher" or declined["origin_lat"] is None:
        return None
    tried = {
        r["hospital_id"]
        for r in conn.execute(
            "select hospital_id::text from holds where route_chain_id = %s", (declined["route_chain_id"],)
        ).fetchall()
    }
    candidates = rank_candidates(
        conn, lat=declined["origin_lat"], lng=declined["origin_lng"], ward=declined["ward"], exclude=tuple(tried)
    )
    for c in candidates:
        try:
            with conn.transaction():
                return create_hold(
                    conn,
                    actor=actor,
                    hospital_id=c["hospital_id"],
                    ward=declined["ward"],
                    source="dispatcher",
                    severity=declined["severity"],
                    condition_category=declined["condition_category"],
                    condition_note=declined["condition_note"],
                    age_group=declined["age_group"],
                    sex=declined["sex"],
                    dispatcher_user_id=str(declined["dispatcher_user_id"]) if declined["dispatcher_user_id"] else None,
                    agency_id=str(declined["agency_id"]) if declined["agency_id"] else None,
                    origin=(declined["origin_lat"], declined["origin_lng"]),
                    eta=c["eta_minutes"],
                    route_chain_id=str(declined["route_chain_id"]),
                    previous_hold_id=str(declined["id"]),
                )
        except HTTPException:
            continue  # filled up in the meantime — try the next one
    audit(conn, "system", "hold.reroute_failed", "hold", declined["id"])
    return None


# ---------------------------------------------------------------- ward updates


def update_ward(conn: Connection, *, hospital_id: str, kind: str, actor: str,
                occupied=None, free=None, free_delta=None, total=None) -> dict:
    """`free` / `free_delta` are PHYSICALLY empty beds as staff see them on the
    ward (beds held for incoming patients still count as physically empty)."""
    if kind not in WARD_KINDS:
        raise HTTPException(422, f"Unknown ward '{kind}'")
    given = [v is not None for v in (occupied, free, free_delta)]
    if sum(given) > 1 or (sum(given) == 0 and total is None):
        raise HTTPException(422, "Send exactly one of occupied, free or free_delta (and/or total)")
    w = conn.execute(
        "select * from wards where hospital_id = %s and kind = %s for update", (hospital_id, kind)
    ).fetchone()
    if not w:
        if total is None:
            raise HTTPException(404, f"This hospital has no {kind} ward yet; send 'total' to create it")
        w = conn.execute(
            "insert into wards (hospital_id, kind, total, occupied, updated_by) values (%s, %s, %s, 0, %s) returning *",
            (hospital_id, kind, total, actor),
        ).fetchone()
    new_total = w["total"] if total is None else total
    if new_total < 0:
        raise HTTPException(422, "total cannot be negative")
    if occupied is not None:
        new_occ = occupied
    elif free is not None:
        new_occ = new_total - free
    elif free_delta is not None:
        new_occ = w["occupied"] - free_delta
    else:
        new_occ = w["occupied"]
    if not 0 <= new_occ <= new_total:
        raise HTTPException(422, f"Occupied beds must be between 0 and {new_total}")
    conn.execute(
        "update wards set total = %s, occupied = %s, updated_at = now(), updated_by = %s where id = %s",
        (new_total, new_occ, actor, w["id"]),
    )
    audit(conn, actor, "ward.updated", "ward", w["id"], hospital_id=hospital_id, kind=kind,
          total=new_total, occupied=new_occ)
    return wards_for(conn, [hospital_id])[hospital_id]

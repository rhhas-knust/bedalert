"""USSD for people with no smartphone or no data.

Speaks the Africa's Talking USSD callback format: the gateway POSTs
sessionId, serviceCode, phoneNumber and `text` (every answer so far joined
with '*'), and we reply with plain text starting with "CON " (more input
needed) or "END " (session over).

Because `text` carries the whole conversation, this handler keeps no session
state. Menus stay short: USSD screens are small and telcos end sessions after
a minute or two, so the hold code is also sent by SMS.

Set the callback URL at the aggregator to  /v1/ussd?key=<USSD_CALLBACK_SECRET>
"""

import hmac
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query
from fastapi.responses import PlainTextResponse
from psycopg import Connection

from ..config import settings
from ..db import get_db
from ..ledger import create_hold, public_facilities
from ..util import normalize_phone

router = APIRouter(prefix="/v1", tags=["ussd"])

MORE = "98"
BACK_TO_START = "0"

CATEGORIES = {
    "emergency": [
        ("chest_pain", "Chest pain"),
        ("road_accident", "Accident"),
        ("labour", "Labour"),
        ("breathing_difficulty", "Breathing"),
        ("bleeding_injury", "Bleeding/injury"),
        ("other", "Other"),
    ],
    "stable": [
        ("referral", "Referral/check-up"),
        ("child_fever", "Child fever"),
        ("other", "Other"),
    ],
}


class Reply(Exception):
    def __init__(self, text: str):
        self.text = text


def _pick(inputs: list, pos: int, items: list, title: str, label, per_page: int):
    """Consume answers at inputs[pos:] for a paged menu. Returns
    (chosen_item, next_pos) or raises Reply with the menu to show."""
    page = 0
    while pos < len(inputs) and inputs[pos] == MORE:
        page += 1
        pos += 1
    start = page * per_page
    shown = items[start:start + per_page]
    if pos >= len(inputs):
        lines = [title] + [f"{i + 1}. {label(it)}" for i, it in enumerate(shown)]
        if start + per_page < len(items):
            lines.append(f"{MORE}. More")
        lines.append(f"{BACK_TO_START}. Start again")
        raise Reply("CON " + "\n".join(lines))
    try:
        choice = int(inputs[pos])
        if not 1 <= choice <= len(shown):
            raise ValueError
    except ValueError:
        raise Reply("END Invalid choice. Please dial again.")
    return shown[choice - 1], pos + 1


def ussd_flow(db: Connection, phone: str, text: str) -> str:
    inputs = [t.strip() for t in text.split("*")] if text else []
    # "0" anywhere restarts: keep only what came after the last one.
    if BACK_TO_START in inputs:
        inputs = inputs[len(inputs) - inputs[::-1].index(BACK_TO_START):]
    try:
        kind, pos = _pick(
            inputs, 0, ["emergency", "stable"],
            "BedAlert - find a hospital bed", 
            lambda k: "Emergency" if k == "emergency" else "Non-emergency (ward)", 2,
        )
        ward = "ER" if kind == "emergency" else "general"

        regions = sorted({f["region"] for f in public_facilities(db, ward=ward)})
        if not regions:
            return "END No hospitals are available on BedAlert yet. Emergency? Call 112."
        region, pos = _pick(inputs, pos, regions, "Your region:", str, 6)

        facilities = public_facilities(db, ward=ward, region=region)
        facilities.sort(key=lambda f: (-f["wards"][0]["available"], not f["wards"][0]["fresh"]))

        def hospital_label(f):
            w = f["wards"][0]
            return f"{f['name'][:22]} {w['available']} free" + ("" if w["fresh"] else "?")

        hospital, pos = _pick(inputs, pos, facilities, f"{ward} beds ('?' = not confirmed recently):", hospital_label, 4)
        if hospital["wards"][0]["available"] <= 0:
            return f"END No free {ward} beds at {hospital['name']}. Dial again to pick another hospital. Emergency? Call 112."

        category, pos = _pick(inputs, pos, CATEGORIES[kind], "What is the problem?", lambda c: c[1], 6)
    except Reply as r:
        return r.text

    try:
        with db.transaction():
            hold = create_hold(
                db,
                actor=f"citizen:{phone}",
                hospital_id=hospital["id"],
                ward=ward,
                source="ussd",
                severity="severe" if kind == "emergency" else "stable",
                condition_category=category[0],
                citizen_phone=phone,
            )
    except HTTPException as exc:
        if exc.status_code == 409 and "already have" in str(exc.detail):
            existing = db.execute(
                """select x.code, h.name from holds x join hospitals h on h.id = x.hospital_id
                   where x.citizen_phone = %s and x.status in ('held', 'accepted')""",
                (phone,),
            ).fetchone()
            if existing:
                return f"END You already have a bed held at {existing['name']}, code {existing['code']}."
        return f"END {exc.detail}. Emergency? Call 112."
    phone_line = f" Tel {hospital['phone']}." if hospital.get("phone") else ""
    return (
        f"END Bed held at {hospital['name']}. Code {hold['code']}. Go now.{phone_line} "
        "Code also sent by SMS. Emergency? Call 112."
    )


@router.post("/ussd", response_class=PlainTextResponse)
def ussd_callback(
    key: str = Query(""),
    sessionId: str = Form(""),
    serviceCode: str = Form(""),
    phoneNumber: str = Form(...),
    text: Optional[str] = Form(""),
    db: Connection = Depends(get_db, scope="function"),
):
    if not hmac.compare_digest(key.encode(), settings.ussd_callback_secret.encode()):
        raise HTTPException(403, "Bad USSD callback key")
    try:
        phone = normalize_phone(phoneNumber)
    except HTTPException:
        return "END Sorry, we could not read your phone number."
    return ussd_flow(db, phone, text or "")

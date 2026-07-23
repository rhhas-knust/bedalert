"""
BedAlert API — demo backend (mock data, in-memory).

Serves the shared bed-availability data layer for all three BedAlert tiers:
  1. Web dashboard  (public view + dispatcher console + hospital admin)
  2. SMS/USSD layer (via /api/sms, simulating a telco gateway callback)
  3. Hospital API    (this service itself — anonymous, aggregate-only)

Privacy constraint (hard requirement): this API never stores or returns
individual patient records — only bed COUNTS and AGGREGATE demographic
buckets (age group + sex). See mock_data.py for the data shape.

Run:
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000
"""

import math
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from mock_data import HOSPITALS, ALERTS, EMERGENCY_LOG, SURGE_THRESHOLD

app = FastAPI(title="BedAlert API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo only — restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)

BOOKINGS: list = []
SMS_SESSIONS: dict = {}


# ---------- schemas ----------

class BedUpdate(BaseModel):
    available_beds: Optional[int] = None
    delta: Optional[int] = None
    department: str = "general"


class BookingRequest(BaseModel):
    hospital_id: str
    age_group: str
    sex: str
    condition_notes: str  # required — the reason/problem must always be stated
    booking_type: str = "stable"  # "stable" | "emergency"

    @field_validator("condition_notes")
    @classmethod
    def notes_required(cls, v):
        if not v or not v.strip():
            raise ValueError("condition_notes is required and cannot be empty")
        return v.strip()

    @field_validator("booking_type")
    @classmethod
    def valid_type(cls, v):
        if v not in ("stable", "emergency"):
            raise ValueError("booking_type must be 'stable' or 'emergency'")
        return v


class EmergencyRequest(BaseModel):
    lat: float
    lng: float
    severity: str  # "critical" | "severe" | "moderate"
    department_needed: str = "ER"
    condition_notes: str = ""


class SmsRequest(BaseModel):
    phone: str
    text: str


class DoctorEntry(BaseModel):
    name: str
    specialty: str
    on_call: bool = False


class DeptCapacity(BaseModel):
    total: int
    available: int


class HospitalRegistration(BaseModel):
    name: str
    city: str
    country: str
    lat: float
    lng: float
    er_total: int = 10
    icu_total: int = 5
    general_total: int = 20
    doctors: List[DoctorEntry] = []


# ---------- helpers ----------

def now_iso():
    return datetime.now(timezone.utc).isoformat()


def haversine_km(lat1, lng1, lat2, lng2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    )
    return 2 * R * math.asin(math.sqrt(a))


def check_surge(hospital):
    """Raise a surge alert if any department crosses the occupancy threshold."""
    for dept_name, dept in hospital["departments"].items():
        if dept["total"] == 0:
            continue
        occupancy = 1 - (dept["available"] / dept["total"])
        if occupancy >= SURGE_THRESHOLD:
            ALERTS.insert(0, {
                "id": str(uuid.uuid4())[:8],
                "hospital_id": hospital["id"],
                "hospital_name": hospital["name"],
                "department": dept_name,
                "occupancy_pct": round(occupancy * 100, 1),
                "created_at": now_iso(),
            })


def pick_on_call_doctor(hospital):
    for doc in hospital.get("doctors", []):
        if doc.get("on_call"):
            return doc
    return hospital["doctors"][0] if hospital.get("doctors") else None


def notify_hospital(hospital, *, source, severity, condition_notes, code):
    """Simulates an SMS being sent to the hospital and logs an emergency-code
    notification doctors on site can see on the Admin page."""
    doctor = pick_on_call_doctor(hospital)
    entry = {
        "code": code,
        "source": source,           # "dispatcher" | "public" | "sms"
        "severity": severity,
        "condition_notes": condition_notes,
        "notified_doctor": doctor["name"] if doctor else "No doctor on call",
        "created_at": now_iso(),
    }
    hospital.setdefault("notifications", []).insert(0, entry)
    EMERGENCY_LOG.insert(0, {
        "code": code,
        "hospital_id": hospital["id"],
        "hospital_name": hospital["name"],
        "source": source,
        "severity": severity,
        "condition_notes": condition_notes,
        "created_at": now_iso(),
    })
    return entry


# ---------- hospital / bed endpoints ----------

@app.get("/api/hospitals")
def list_hospitals():
    return list(HOSPITALS.values())


@app.get("/api/hospitals/{hospital_id}")
def get_hospital(hospital_id: str):
    hospital = HOSPITALS.get(hospital_id)
    if not hospital:
        raise HTTPException(404, "Hospital not found")
    return hospital


@app.post("/api/hospitals")
def register_hospital(reg: HospitalRegistration):
    """Lets a new hospital register itself into the network."""
    new_id = f"h{len(HOSPITALS) + 1}_{str(uuid.uuid4())[:4]}"
    hospital = {
        "id": new_id,
        "name": reg.name,
        "city": reg.city,
        "country": reg.country,
        "lat": reg.lat,
        "lng": reg.lng,
        "departments": {
            "ER": {"total": reg.er_total, "available": reg.er_total},
            "ICU": {"total": reg.icu_total, "available": reg.icu_total},
            "general": {"total": reg.general_total, "available": reg.general_total},
        },
        "demographics": {
            "age_groups": {"0-17": 0, "18-39": 0, "40-64": 0, "65+": 0},
            "sex": {"female": 0, "male": 0, "other_unspecified": 0},
        },
        "doctors": [d.model_dump() for d in reg.doctors],
        "notifications": [],
        "last_updated": now_iso(),
    }
    HOSPITALS[new_id] = hospital
    return hospital


@app.post("/api/hospitals/{hospital_id}/beds")
def update_beds(hospital_id: str, update: BedUpdate):
    """The 'tap button' endpoint — hospital staff increment/decrement bed counts."""
    hospital = HOSPITALS.get(hospital_id)
    if not hospital:
        raise HTTPException(404, "Hospital not found")
    dept = hospital["departments"].get(update.department)
    if not dept:
        raise HTTPException(400, f"Unknown department '{update.department}'")

    if update.delta is not None:
        dept["available"] = max(0, min(dept["total"], dept["available"] + update.delta))
    elif update.available_beds is not None:
        dept["available"] = max(0, min(dept["total"], update.available_beds))
    else:
        raise HTTPException(400, "Provide either 'delta' or 'available_beds'")

    hospital["last_updated"] = now_iso()
    check_surge(hospital)
    return hospital


@app.get("/api/alerts")
def get_alerts():
    return ALERTS[:20]


@app.get("/api/emergency-log")
def get_emergency_log():
    """Shared live feed of emergencies raised from ANY tier — public booking,
    SMS/USSD, or the dispatcher console — so all three surfaces stay in sync."""
    return EMERGENCY_LOG[:30]


# ---------- public booking (stable + self-reported emergency) ----------

@app.post("/api/bookings")
def create_booking(req: BookingRequest):
    hospital = HOSPITALS.get(req.hospital_id)
    if not hospital:
        raise HTTPException(404, "Hospital not found")

    dept_name = "ER" if req.booking_type == "emergency" else "general"
    dept = hospital["departments"][dept_name]
    if dept["available"] <= 0:
        raise HTTPException(400, f"No {dept_name} beds available at this hospital")

    dept["available"] -= 1
    hospital["last_updated"] = now_iso()
    check_surge(hospital)

    code = str(uuid.uuid4())[:6].upper()
    booking = {
        "id": str(uuid.uuid4())[:8],
        "hospital_id": hospital["id"],
        "hospital_name": hospital["name"],
        "age_group": req.age_group,
        "sex": req.sex,
        "condition_notes": req.condition_notes,
        "booking_type": req.booking_type,
        "status": "confirmed",
        "code": code,
        "created_at": now_iso(),
    }
    BOOKINGS.append(booking)

    if req.booking_type == "emergency":
        notify_hospital(
            hospital,
            source="public",
            severity="self-reported emergency",
            condition_notes=req.condition_notes,
            code=code,
        )

    return booking


@app.get("/api/bookings")
def list_bookings():
    return BOOKINGS


@app.get("/api/hospitals/{hospital_id}/bookings")
def hospital_bookings(hospital_id: str):
    if hospital_id not in HOSPITALS:
        raise HTTPException(404, "Hospital not found")
    return [b for b in BOOKINGS if b["hospital_id"] == hospital_id]


# ---------- dispatcher: emergency redirect ----------

@app.post("/api/dispatch/emergency")
def dispatch_emergency(req: EmergencyRequest):
    """Finds the nearest hospital with capacity in the needed department,
    reserves a bed, and notifies that hospital (surge check + doctor alert)."""
    # Critical cases always route to Emergency, regardless of what was selected client-side
    department = "ER" if req.severity == "critical" else req.department_needed

    candidates = []
    for hospital in HOSPITALS.values():
        dept = hospital["departments"].get(department)
        if dept and dept["available"] > 0:
            dist = haversine_km(req.lat, req.lng, hospital["lat"], hospital["lng"])
            candidates.append((dist, hospital))

    if not candidates:
        raise HTTPException(404, "No hospitals with capacity found for this department")

    candidates.sort(key=lambda pair: pair[0])
    dist_km, chosen = candidates[0]
    dept = chosen["departments"][department]
    dept["available"] -= 1
    chosen["last_updated"] = now_iso()
    check_surge(chosen)

    code = str(uuid.uuid4())[:6].upper()
    notification = notify_hospital(
        chosen,
        source="dispatcher",
        severity=req.severity,
        condition_notes=req.condition_notes,
        code=code,
    )

    return {
        "dispatch_id": str(uuid.uuid4())[:8],
        "hospital_id": chosen["id"],
        "hospital_name": chosen["name"],
        "department": department,
        "distance_km": round(dist_km, 1),
        "severity": req.severity,
        "eta_minutes_estimate": round(dist_km / 0.6),  # rough ~36km/h avg ambulance speed
        "emergency_code": code,
        "notified_doctor": notification["notified_doctor"],
        "created_at": now_iso(),
    }


# ---------- SMS / USSD gateway simulation ----------
# Flow: issue type (emergency / regular) -> locality/municipality -> hospital
# list for that locality -> reason for visit -> auto-book + SMS the hospital.

MENU_ROOT = (
    "BedAlert\n"
    "1. Report an emergency\n"
    "2. Book a stable-case bed"
)


def cities_available():
    return sorted({h["city"] for h in HOSPITALS.values()})


def hospitals_in_city(city):
    return [h for h in HOSPITALS.values() if h["city"] == city]


def process_sms(text: str, session: dict):
    state = session.get("state", "root")
    text = text.strip()

    if text in ("*123#", "start", ""):
        session.clear()
        session["state"] = "root"
        return MENU_ROOT, session

    if text == "0":
        session.clear()
        session["state"] = "root"
        return MENU_ROOT, session

    if state == "root":
        if text in ("1", "2"):
            session["booking_type"] = "emergency" if text == "1" else "stable"
            session["state"] = "reason"
            prompt = "car accident, birth, chest pain, etc" if text == "1" else "checkup, referral, etc"
            return f"Briefly describe the issue ({prompt}):", session
        return "Invalid option.\n\n" + MENU_ROOT, session

    if state == "reason":
        if not text:
            return "Please describe the issue in a few words:", session
        session["condition_notes"] = text
        cities = cities_available()
        session["city_order"] = cities
        session["state"] = "locality"
        lines = [f"{i+1}. {c}" for i, c in enumerate(cities)]
        return "Select your municipality/locality:\n" + "\n".join(lines), session

    if state == "locality":
        try:
            idx = int(text) - 1
            city = session["city_order"][idx]
        except (ValueError, IndexError):
            return "Invalid selection. Reply 0 for menu.", session
        session["city"] = city
        options = hospitals_in_city(city)
        dept = "ER" if session["booking_type"] == "emergency" else "general"
        session["hosp_order"] = [h["id"] for h in options]
        lines = []
        for i, h in enumerate(options):
            d = h["departments"][dept]
            lines.append(f"{i+1}. {h['name']} ({d['available']} beds free)")
        session["state"] = "hospital_select"
        return f"Hospitals in {city}:\n" + "\n".join(lines) + "\nReply 0 for menu.", session

    if state == "hospital_select":
        try:
            idx = int(text) - 1
            hid = session["hosp_order"][idx]
            hospital = HOSPITALS[hid]
        except (ValueError, IndexError, KeyError):
            return "Invalid selection. Reply 0 for menu.", session

        booking_type = session["booking_type"]
        dept_name = "ER" if booking_type == "emergency" else "general"
        dept = hospital["departments"][dept_name]
        if dept["available"] <= 0:
            session["state"] = "root"
            return f"No beds free at {hospital['name']} right now. Reply 0 for menu.", session

        dept["available"] -= 1
        hospital["last_updated"] = now_iso()
        check_surge(hospital)

        code = str(uuid.uuid4())[:6].upper()
        BOOKINGS.append({
            "id": str(uuid.uuid4())[:8],
            "hospital_id": hospital["id"],
            "hospital_name": hospital["name"],
            "age_group": "unknown",
            "sex": "unspecified",
            "condition_notes": session.get("condition_notes", ""),
            "booking_type": booking_type,
            "status": "confirmed",
            "code": code,
            "created_at": now_iso(),
        })
        notify_hospital(
            hospital,
            source="sms",
            severity="emergency" if booking_type == "emergency" else "stable booking",
            condition_notes=session.get("condition_notes", ""),
            code=code,
        )

        reply = (
            f"Booked at {hospital['name']}. Code {code}.\n"
            f"An SMS has been sent to the hospital to prepare for you.\n"
            f"Reply 0 for menu."
        )
        session["state"] = "root"
        return reply, session

    session["state"] = "root"
    return MENU_ROOT, session


@app.post("/api/sms")
def sms_gateway(req: SmsRequest):
    """Simulates the telco SMS/USSD gateway webhook. In production this
    endpoint would be called by the SMS/USSD aggregator (e.g. Africa's
    Talking, Twilio) on each inbound message/session step."""
    session = SMS_SESSIONS.get(req.phone, {"state": "root"})
    reply, session = process_sms(req.text, session)
    SMS_SESSIONS[req.phone] = session
    return {"reply": reply}


@app.get("/api/health")
def health():
    return {"status": "ok", "time": now_iso()}

import os

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/bedalert_test")
os.environ["BEDALERT_ENV"] = "dev"
os.environ["SMS_WORKER"] = "0"

import psycopg  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from scripts.migrate import migrate  # noqa: E402

DB_URL = os.environ["DATABASE_URL"]
TABLES = "audit_log, sms_outbox, otp_codes, api_keys, holds, memberships, staff, agencies, on_call_contacts, wards, hospitals"


@pytest.fixture(scope="session", autouse=True)
def schema():
    with psycopg.connect(DB_URL, autocommit=True) as conn:
        conn.execute("drop schema public cascade; create schema public;")
    migrate(DB_URL)


@pytest.fixture()
def db():
    with psycopg.connect(DB_URL, autocommit=True) as conn:
        conn.execute(f"truncate {TABLES} cascade")
        yield conn


@pytest.fixture()
def client(db):
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------- helpers


def add_hospital(db, name, *, lat=6.69, lng=-1.62, region="Ashanti", status="verified", wards=None, phone="+233322000001"):
    hid = db.execute(
        """insert into hospitals (name, region, district, city, lat, lng, phone, license_number, status)
           values (%s, %s, 'D', 'City', %s, %s, %s, 'L1', %s) returning id::text""",
        (name, region, lat, lng, phone, status),
    ).fetchone()[0]
    for kind, (total, occupied) in (wards or {"ER": (5, 3), "general": (10, 5)}).items():
        db.execute("insert into wards (hospital_id, kind, total, occupied) values (%s, %s, %s, %s)", (hid, kind, total, occupied))
    db.execute(
        "insert into on_call_contacts (hospital_id, name, phone) values (%s, 'Dr On Call', '+233200000999')", (hid,)
    )
    return hid


def staff_headers(client, email):
    token = client.post("/v1/dev/staff-token", json={"email": email}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def make_staff(client, db, email, role, *, hospital_id=None, agency_id=None):
    headers = staff_headers(client, email)
    uid = client.get("/v1/me", headers=headers).json()["user_id"]  # creates the staff row
    db.execute(
        "insert into memberships (user_id, role, hospital_id, agency_id) values (%s, %s, %s, %s)",
        (uid, role, hospital_id, agency_id),
    )
    return headers


def citizen_headers(client, phone="0241234567"):
    code = client.post("/v1/auth/otp/request", json={"phone": phone}).json()["dev_code"]
    token = client.post("/v1/auth/otp/verify", json={"phone": phone, "code": code}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def available(client, hospital_id, ward):
    f = client.get(f"/v1/facilities/{hospital_id}").json()
    return next(w["available"] for w in f["wards"] if w["kind"] == ward)

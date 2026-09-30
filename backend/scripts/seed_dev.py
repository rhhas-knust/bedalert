"""DEV ONLY: load demo hospitals, a dispatch agency and demo staff so the API
can be tried locally. Refuses to run unless BEDALERT_ENV=dev, because fake bed
numbers for real hospital names must never reach the public.

    python -m scripts.seed_dev
"""

import pathlib
import sys
import uuid

import psycopg

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from app.config import settings  # noqa: E402

# Approximate coordinates. Bed numbers are made up.
HOSPITALS = [
    ("Korle Bu Teaching Hospital (DEMO)", "Greater Accra", "Ablekuma South", "Accra", 5.5364, -0.2279, "+233302000001",
     {"ER": (30, 26), "ICU": (12, 11), "general": (120, 101), "maternity": (40, 33)}),
    ("Greater Accra Regional Hospital, Ridge (DEMO)", "Greater Accra", "Osu Klottey", "Accra", 5.5631, -0.1966, "+233302000002",
     {"ER": (20, 17), "ICU": (8, 8), "general": (80, 70), "maternity": (30, 22)}),
    ("37 Military Hospital (DEMO)", "Greater Accra", "Ayawaso East", "Accra", 5.5875, -0.1848, "+233302000003",
     {"ER": (25, 19), "ICU": (10, 9), "general": (100, 88)}),
    ("Komfo Anokye Teaching Hospital (DEMO)", "Ashanti", "Kumasi Metro", "Kumasi", 6.6975, -1.6295, "+233322000001",
     {"ER": (30, 27), "ICU": (12, 12), "general": (150, 131), "maternity": (50, 41)}),
    ("KNUST Hospital (DEMO)", "Ashanti", "Oforikrom", "Kumasi", 6.6800, -1.5700, "+233322000002",
     {"ER": (10, 6), "general": (40, 29)}),
    ("Tamale Teaching Hospital (DEMO)", "Northern", "Tamale Metro", "Tamale", 9.3930, -0.8390, "+233372000001",
     {"ER": (20, 18), "ICU": (6, 6), "general": (90, 80), "maternity": (30, 25)}),
]

STAFF = [
    ("admin@bedalert.dev", "network_admin", None),
    ("dispatch.ashanti@bedalert.dev", "dispatcher", "agency"),
    ("nurse.kath@bedalert.dev", "hospital_staff", "Komfo Anokye Teaching Hospital (DEMO)"),
    ("admin.kath@bedalert.dev", "hospital_admin", "Komfo Anokye Teaching Hospital (DEMO)"),
]


def dev_user_id(email: str) -> str:
    # Same derivation as the /v1/dev/staff-token route.
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"bedalert-dev:{email.lower()}"))


def seed(database_url: str = settings.database_url) -> None:
    if not settings.is_dev:
        raise SystemExit("Refusing to seed demo data outside BEDALERT_ENV=dev")
    with psycopg.connect(database_url) as conn:
        if conn.execute("select count(*) from hospitals").fetchone()[0]:
            print("Hospitals already present; skipping seed.")
            return
        ids = {}
        for name, region, district, city, lat, lng, phone, wards in HOSPITALS:
            hid = conn.execute(
                """insert into hospitals (name, region, district, city, lat, lng, phone, license_number, status, verified_at)
                   values (%s, %s, %s, %s, %s, %s, %s, 'DEMO', 'verified', now()) returning id""",
                (name, region, district, city, lat, lng, phone),
            ).fetchone()[0]
            ids[name] = hid
            for kind, (total, occupied) in wards.items():
                conn.execute(
                    "insert into wards (hospital_id, kind, total, occupied, updated_by) values (%s, %s, %s, %s, 'seed')",
                    (hid, kind, total, occupied),
                )
            conn.execute(
                "insert into on_call_contacts (hospital_id, name, role, phone) values (%s, 'Duty doctor (demo)', 'doctor', %s)",
                (hid, phone),
            )
        agency = conn.execute(
            "insert into agencies (name, region) values ('National Ambulance Service - Ashanti (DEMO)', 'Ashanti') returning id"
        ).fetchone()[0]
        for email, role, target in STAFF:
            uid = dev_user_id(email)
            conn.execute("insert into staff (user_id, email) values (%s, %s) on conflict do nothing", (uid, email))
            conn.execute(
                "insert into memberships (user_id, role, hospital_id, agency_id) values (%s, %s, %s, %s)",
                (uid, role, ids.get(target) if role.startswith("hospital") else None, agency if role == "dispatcher" else None),
            )
    print(f"Seeded {len(HOSPITALS)} demo hospitals, 1 agency, {len(STAFF)} staff. Log in via POST /v1/dev/staff-token.")


if __name__ == "__main__":
    seed()

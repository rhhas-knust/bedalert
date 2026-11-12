"""Bootstrap: give a Supabase user a role (e.g. the first network admin).

    python -m scripts.grant_role --user-id <auth user uuid> --email you@example.com --role network_admin
"""

import argparse
import os

import psycopg

p = argparse.ArgumentParser()
p.add_argument("--user-id", required=True, help="Supabase auth.users.id")
p.add_argument("--email", required=True)
p.add_argument("--role", required=True, choices=["network_admin", "hospital_admin", "hospital_staff", "dispatcher"])
p.add_argument("--hospital-id")
p.add_argument("--agency-id")
a = p.parse_args()

with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
    conn.execute(
        "insert into staff (user_id, email) values (%s, %s) on conflict (user_id) do update set email = excluded.email",
        (a.user_id, a.email),
    )
    conn.execute(
        "insert into memberships (user_id, role, hospital_id, agency_id) values (%s, %s, %s, %s) on conflict do nothing",
        (a.user_id, a.role, a.hospital_id, a.agency_id),
    )
    conn.execute(
        "insert into audit_log (actor, action, entity, entity_id, details) values ('cli', 'membership.granted', 'staff', %s, %s::jsonb)",
        (a.user_id, f'{{"role": "{a.role}"}}'),
    )
print(f"Granted {a.role} to {a.email}")

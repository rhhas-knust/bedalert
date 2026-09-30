"""Apply supabase/migrations/*.sql to DATABASE_URL, in filename order, once each.

For a Supabase project you can use this too (point DATABASE_URL at the
project's connection string), or `supabase db push` from the repo root.

    python -m scripts.migrate
"""

import pathlib
import sys

import psycopg

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from app.config import settings  # noqa: E402

MIGRATIONS = pathlib.Path(__file__).resolve().parents[2] / "supabase" / "migrations"


def migrate(database_url: str = settings.database_url) -> list:
    applied_now = []
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(
            "create table if not exists bedalert_schema_migrations (filename text primary key, applied_at timestamptz default now())"
        )
        conn.execute("alter table bedalert_schema_migrations enable row level security")
        done = {r[0] for r in conn.execute("select filename from bedalert_schema_migrations")}
        for path in sorted(MIGRATIONS.glob("*.sql")):
            if path.name in done:
                continue
            with conn.transaction():
                conn.execute(path.read_text())
                conn.execute("insert into bedalert_schema_migrations (filename) values (%s)", (path.name,))
            applied_now.append(path.name)
    return applied_now


if __name__ == "__main__":
    names = migrate()
    print("Applied: " + (", ".join(names) if names else "nothing (up to date)"))

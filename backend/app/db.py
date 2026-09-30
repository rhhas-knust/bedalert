"""Postgres connection pool.

Each request gets one connection inside one transaction: it commits when the
request handler returns and rolls back if it raises.
"""

from contextlib import contextmanager
from typing import Iterator

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import settings

_pool: ConnectionPool | None = None


def open_pool() -> None:
    global _pool
    _pool = ConnectionPool(settings.database_url, min_size=1, max_size=10, kwargs={"row_factory": dict_row}, open=True)
    _pool.wait()


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def get_db() -> Iterator[Connection]:
    """FastAPI dependency."""
    with _pool.connection() as conn:
        yield conn


@contextmanager
def connection() -> Iterator[Connection]:
    """For code running outside a request (background tasks, scripts)."""
    with _pool.connection() as conn:
        yield conn


def audit(conn: Connection, actor: str, action: str, entity: str, entity_id=None, **details) -> None:
    from psycopg.types.json import Jsonb

    conn.execute(
        "insert into audit_log (actor, action, entity, entity_id, details) values (%s, %s, %s, %s, %s)",
        (actor, action, entity, str(entity_id) if entity_id is not None else None, Jsonb(details)),
    )

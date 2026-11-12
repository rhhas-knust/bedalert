"""Postgres connection pool.

Each request gets one connection inside one transaction: it commits when the
request handler returns and rolls back if it raises.
"""

from contextlib import contextmanager
from typing import Iterator

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

import threading

from .config import settings

_pool: ConnectionPool | None = None
_pool_lock = threading.Lock()


def _uses_transaction_pooler(url: str) -> bool:
    # Supabase's transaction pooler (Supavisor, port 6543) hands each
    # transaction to any server connection, so server-side prepared
    # statements must be off. Serverless hosts (Vercel) should use it.
    return ":6543" in url or settings.db_pooler == "transaction"


def open_pool() -> None:
    global _pool
    with _pool_lock:
        if _pool is not None:
            return
        kwargs = {"row_factory": dict_row}
        if _uses_transaction_pooler(settings.database_url):
            kwargs["prepare_threshold"] = None
        _pool = ConnectionPool(
            settings.database_url,
            min_size=1,
            max_size=settings.db_pool_max,
            kwargs=kwargs,
            open=True,
        )
    _pool.wait()


def _get_pool() -> ConnectionPool:
    # Serverless platforms may not run the lifespan hook before the first
    # request, so open the pool lazily too.
    if _pool is None:
        open_pool()
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def get_db() -> Iterator[Connection]:
    """FastAPI dependency."""
    with _get_pool().connection() as conn:
        yield conn


@contextmanager
def connection() -> Iterator[Connection]:
    """For code running outside a request (background tasks, scripts)."""
    with _get_pool().connection() as conn:
        yield conn


def audit(conn: Connection, actor: str, action: str, entity: str, entity_id=None, **details) -> None:
    from psycopg.types.json import Jsonb

    conn.execute(
        "insert into audit_log (actor, action, entity, entity_id, details) values (%s, %s, %s, %s, %s)",
        (actor, action, entity, str(entity_id) if entity_id is not None else None, Jsonb(details)),
    )

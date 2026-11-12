"""BedAlert core API.

One API, one bed ledger, several kinds of caller — each with its own app and
credential:

  /v1/facilities, /v1/regions, /v1/meta   public (no login)
  /v1/auth/otp/*, /v1/holds               citizens (phone OTP)
  /v1/ussd                                feature phones via USSD aggregator
  /v1/me, /v1/hospital/*                  hospital portal (staff login)
  /v1/integrations/*                      hospital systems (API key)
  /v1/dispatch/*                          dispatch console (staff login)
  /v1/admin/*                             BedAlert network admin

Privacy rule: public routes return bed counts only — never patients,
condition details, phone numbers or staff names.
"""

import logging
import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from psycopg import errors

from .config import settings
from .db import close_pool, connection, open_pool
from .routers import admin, citizen, dispatch, hospital, integrations, public, ussd
from .sms import flush_outbox, request_sms_flag, run_outbox_worker

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    open_pool()
    stop = threading.Event()
    worker = None
    # A background thread only makes sense on a host that keeps the process
    # running. Vercel sets VERCEL=1 and pauses functions between requests.
    worker_default = "0" if os.environ.get("VERCEL") else "1"
    if os.environ.get("SMS_WORKER", worker_default) == "1":
        worker = threading.Thread(target=run_outbox_worker, args=(stop,), daemon=True, name="sms-outbox")
        worker.start()
    yield
    stop.set()
    if worker:
        worker.join(timeout=5)
    close_pool()


app = FastAPI(title="BedAlert API", version="1.0.0-phase1", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def flush_sms_after_request(request: Request, call_next):
    """Send the SMS a request queued once its transaction has committed.

    The DB dependency commits when the endpoint returns, before the response
    is handed back here, so the messages are already visible to
    flush_outbox. Sending inline adds about a second to requests that text
    someone, and means no message waits for a background worker.
    """
    flag = {"queued": False}
    token = request_sms_flag.set(flag)
    try:
        response = await call_next(request)
    finally:
        request_sms_flag.reset(token)
    if flag["queued"]:
        try:
            await run_in_threadpool(flush_outbox)
        except Exception:  # noqa: BLE001 — the cron job will retry
            logging.getLogger("bedalert.sms").exception("Inline SMS flush failed")
    return response


@app.exception_handler(errors.InvalidTextRepresentation)
async def bad_id(request: Request, exc: errors.InvalidTextRepresentation):
    # e.g. a malformed UUID in the URL
    return JSONResponse({"detail": "Not found"}, status_code=404)


for r in (public, citizen, ussd, hospital, integrations, dispatch, admin):
    app.include_router(r.router)

if settings.is_dev:
    from .routers import dev

    app.include_router(dev.router)


@app.get("/v1/cron/flush-sms", include_in_schema=False)
def cron_flush_sms(authorization: str = Header(default="")):
    """Safety net for messages a request could not send (provider down,
    function timed out). Called by Vercel Cron, see backend/vercel.json."""
    if not settings.cron_secret or authorization != f"Bearer {settings.cron_secret}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"sent": flush_outbox(limit=200)}


@app.get("/v1/health", tags=["public"])
def health():
    with connection() as conn:
        conn.execute("select 1")
    return {"status": "ok", "env": settings.env}

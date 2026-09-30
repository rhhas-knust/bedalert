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

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from psycopg import errors

from .config import settings
from .db import close_pool, connection, open_pool
from .routers import admin, citizen, dispatch, hospital, integrations, public, ussd
from .sms import run_outbox_worker

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    open_pool()
    stop = threading.Event()
    worker = None
    if os.environ.get("SMS_WORKER", "1") == "1":
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


@app.exception_handler(errors.InvalidTextRepresentation)
async def bad_id(request: Request, exc: errors.InvalidTextRepresentation):
    # e.g. a malformed UUID in the URL
    return JSONResponse({"detail": "Not found"}, status_code=404)


for r in (public, citizen, ussd, hospital, integrations, dispatch, admin):
    app.include_router(r.router)

if settings.is_dev:
    from .routers import dev

    app.include_router(dev.router)


@app.get("/v1/health", tags=["public"])
def health():
    with connection() as conn:
        conn.execute("select 1")
    return {"status": "ok", "env": settings.env}

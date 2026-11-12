"""Machine-to-machine API for hospital information systems (HIS).

Authenticate with `Authorization: Bearer ba_live_...` — a key created by the
hospital's admin in the portal. A key only ever acts on its own hospital.
"""

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection
from pydantic import BaseModel, Field

from ..auth import ApiKeyCaller, current_api_key
from ..db import get_db
from ..ledger import HOLD_SELECT, expire_holds, get_hold_for_update, hold_view, transition_hold, update_ward

router = APIRouter(prefix="/v1/integrations", tags=["hospital integrations"])

WardKind = Literal["ER", "ICU", "general", "maternity", "paediatric"]


class WardCensus(BaseModel):
    occupied: Optional[int] = Field(None, ge=0)
    free: Optional[int] = Field(None, ge=0)
    total: Optional[int] = Field(None, ge=0, le=5000)


@router.put("/wards/{kind}")
def push_census(kind: WardKind, body: WardCensus, key: ApiKeyCaller = Depends(current_api_key),
                db: Connection = Depends(get_db, scope="function")):
    """Send the ward's current numbers from your system (e.g. every few minutes
    or on every admission/discharge)."""
    key.require("beds:write")
    return update_ward(db, hospital_id=key.hospital_id, kind=kind, actor=key.actor, **body.model_dump())


@router.get("/holds")
def list_incoming(status: Literal["active", "all"] = "active",
                  key: ApiKeyCaller = Depends(current_api_key), db: Connection = Depends(get_db, scope="function")):
    key.require("holds:read")
    expire_holds(db)
    where = "x.hospital_id = %s" + (" and x.status in ('held', 'accepted')" if status == "active" else "")
    rows = db.execute(HOLD_SELECT + f" where {where} order by x.created_at desc limit 200", (key.hospital_id,)).fetchall()
    return [hold_view(r, include_private=True) for r in rows]


class Action(BaseModel):
    reason: Optional[str] = Field(None, max_length=200)


@router.post("/holds/{hold_id}/{action}")
def act(hold_id: str, action: Literal["accept", "decline", "arrive"], body: Action = Action(),
        key: ApiKeyCaller = Depends(current_api_key), db: Connection = Depends(get_db, scope="function")):
    key.require("holds:write")
    hold = get_hold_for_update(db, hold_id)
    if str(hold["hospital_id"]) != key.hospital_id:
        raise HTTPException(404, "Hold not found")
    return transition_hold(db, hold, action, actor=key.actor, reason=body.reason)

"""DEV ONLY. Only mounted when BEDALERT_ENV=dev. Stands in for Supabase Auth
so the whole system can be exercised locally without a Supabase project."""

import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from ..auth import issue_staff_token

router = APIRouter(prefix="/v1/dev", tags=["dev only"])


class DevLogin(BaseModel):
    email: str


@router.post("/staff-token")
def staff_token(body: DevLogin):
    """Mint a staff token for any email (stable user id per email)."""
    user_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"bedalert-dev:{body.email.lower()}"))
    return {"access_token": issue_staff_token(user_id, body.email), "token_type": "bearer", "user_id": user_id}

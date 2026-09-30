"""Who is calling?

Three kinds of caller, each with its own credential:

* Staff (hospital staff, dispatchers, BedAlert admins) — a Supabase Auth
  access token (JWT). What they may do comes from `memberships`, never from
  the token itself.
* Citizens — a short-lived BedAlert token obtained with a phone OTP.
* Hospital systems — an API key created in the hospital portal.
"""

import hmac
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from functools import lru_cache
from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException
from psycopg import Connection

from .config import settings
from .db import get_db
from .util import pepper_hash, utcnow

CITIZEN_AUDIENCE = "bedalert-citizen"
ISSUER = "bedalert"

API_KEY_SCOPES = ("beds:write", "holds:read", "holds:write")


def _bearer(authorization: Optional[str]) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing bearer token", headers={"WWW-Authenticate": "Bearer"})
    return authorization[7:].strip()


# ---------------------------------------------------------------- staff


@dataclass
class Membership:
    role: str
    hospital_id: Optional[str]
    agency_id: Optional[str]


@dataclass
class Staff:
    user_id: str
    email: str
    memberships: list = field(default_factory=list)

    @property
    def actor(self) -> str:
        return f"user:{self.user_id}"

    @property
    def is_network_admin(self) -> bool:
        return any(m.role == "network_admin" for m in self.memberships)

    def hospital_role(self, hospital_id: str) -> Optional[str]:
        roles = {m.role for m in self.memberships if m.hospital_id == str(hospital_id)}
        if "hospital_admin" in roles:
            return "hospital_admin"
        if "hospital_staff" in roles:
            return "hospital_staff"
        return None

    def agency_ids(self) -> list:
        return [m.agency_id for m in self.memberships if m.role == "dispatcher"]


@lru_cache(maxsize=1)
def _jwks_client():
    return jwt.PyJWKClient(settings.staff_jwks_url, cache_keys=True)


def decode_staff_token(token: str) -> dict:
    try:
        if settings.staff_jwks_url:
            key = _jwks_client().get_signing_key_from_jwt(token).key
            algorithms = ["RS256", "ES256"]
        else:
            key = settings.staff_jwt_secret
            algorithms = ["HS256"]
        return jwt.decode(
            token,
            key,
            algorithms=algorithms,
            audience=settings.staff_jwt_audience,
            options={"require": ["sub", "exp"]},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(401, f"Invalid staff token: {exc}") from exc


def current_staff(authorization: Optional[str] = Header(None), db: Connection = Depends(get_db, scope="function")) -> Staff:
    claims = decode_staff_token(_bearer(authorization))
    try:
        user_id = str(uuid.UUID(claims["sub"]))
    except ValueError as exc:
        raise HTTPException(401, "Invalid staff token subject") from exc
    email = claims.get("email") or ""
    db.execute(
        """insert into staff (user_id, email) values (%s, %s)
           on conflict (user_id) do update set email = excluded.email
           where staff.email is distinct from excluded.email and excluded.email <> ''""",
        (user_id, email),
    )
    rows = db.execute(
        "select role, hospital_id::text, agency_id::text from memberships where user_id = %s", (user_id,)
    ).fetchall()
    return Staff(user_id=user_id, email=email, memberships=[Membership(**r) for r in rows])


def require_network_admin(staff: Staff = Depends(current_staff)) -> Staff:
    if not staff.is_network_admin:
        raise HTTPException(403, "BedAlert network admin only")
    return staff


def require_dispatcher(staff: Staff = Depends(current_staff)) -> Staff:
    if not staff.agency_ids():
        raise HTTPException(403, "Dispatcher role required")
    return staff


def check_hospital_access(staff: Staff, hospital_id: str, *, admin: bool = False) -> str:
    """Returns the effective role, or raises 403. Network admins may act on any hospital."""
    if staff.is_network_admin:
        return "network_admin"
    role = staff.hospital_role(hospital_id)
    if role is None or (admin and role != "hospital_admin"):
        raise HTTPException(403, "You do not have access to this hospital" if role is None else "Hospital admin only")
    return role


def issue_staff_token(user_id: str, email: str, minutes: int = 60) -> str:
    """DEV ONLY — stands in for Supabase Auth when running locally."""
    now = utcnow()
    return jwt.encode(
        {"sub": user_id, "email": email, "aud": settings.staff_jwt_audience, "role": "authenticated",
         "iat": now, "exp": now + timedelta(minutes=minutes)},
        settings.staff_jwt_secret,
        algorithm="HS256",
    )


# ---------------------------------------------------------------- citizens


@dataclass
class Citizen:
    phone: str

    @property
    def actor(self) -> str:
        return f"citizen:{self.phone}"


def issue_citizen_token(phone: str) -> tuple[str, int]:
    now = utcnow()
    expires_in = settings.citizen_token_minutes * 60
    token = jwt.encode(
        {"sub": phone, "aud": CITIZEN_AUDIENCE, "iss": ISSUER, "iat": now,
         "exp": now + timedelta(seconds=expires_in)},
        settings.citizen_token_secret,
        algorithm="HS256",
    )
    return token, expires_in


def current_citizen(authorization: Optional[str] = Header(None)) -> Citizen:
    try:
        claims = jwt.decode(
            _bearer(authorization),
            settings.citizen_token_secret,
            algorithms=["HS256"],
            audience=CITIZEN_AUDIENCE,
            issuer=ISSUER,
            options={"require": ["sub", "exp"]},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(401, "Please verify your phone number again") from exc
    return Citizen(phone=claims["sub"])


# ---------------------------------------------------------------- hospital API keys


@dataclass
class ApiKeyCaller:
    key_id: str
    hospital_id: str
    prefix: str
    scopes: list

    @property
    def actor(self) -> str:
        return f"api_key:{self.prefix}"

    def require(self, scope: str) -> None:
        if scope not in self.scopes:
            raise HTTPException(403, f"API key is missing scope '{scope}'")


def generate_api_key() -> tuple[str, str]:
    """Returns (full_key, prefix). Format: ba_live_<prefix>_<secret>."""
    prefix = secrets.token_hex(4)
    return f"ba_live_{prefix}_{secrets.token_urlsafe(32)}", prefix


def current_api_key(authorization: Optional[str] = Header(None), db: Connection = Depends(get_db, scope="function")) -> ApiKeyCaller:
    key = _bearer(authorization)
    parts = key.split("_")
    if len(parts) < 4 or parts[0] != "ba" or parts[1] != "live":
        raise HTTPException(401, "Invalid API key")
    prefix = parts[2]
    row = db.execute(
        """select k.id::text, k.hospital_id::text, k.key_hash, k.scopes, h.status
           from api_keys k join hospitals h on h.id = k.hospital_id
           where k.prefix = %s and k.revoked_at is null""",
        (prefix,),
    ).fetchone()
    if not row or not hmac.compare_digest(row["key_hash"], pepper_hash(key)):
        raise HTTPException(401, "Invalid API key")
    if row["status"] == "suspended":
        raise HTTPException(403, "Hospital is suspended from the network")
    db.execute("update api_keys set last_used_at = now() where id = %s", (row["id"],))
    return ApiKeyCaller(key_id=row["id"], hospital_id=row["hospital_id"], prefix=prefix, scopes=list(row["scopes"]))

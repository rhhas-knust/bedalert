import hashlib
import hmac
import math
import re
import secrets
from datetime import datetime, timezone

from fastapi import HTTPException

from .config import settings

# No 0/O, 1/I/L — codes get read out over the phone and typed on keypads.
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_code(length: int = 6) -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))


def pepper_hash(value: str) -> str:
    """Keyed hash for secrets we must verify but never store (API keys, OTPs)."""
    return hmac.new(settings.hash_pepper.encode(), value.encode(), hashlib.sha256).hexdigest()


def normalize_phone(raw: str) -> str:
    """Normalise to E.164. Ghanaian local numbers (024…, 24…) become +233…."""
    digits = re.sub(r"[\s\-()]", "", raw or "")
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    if re.fullmatch(r"0\d{9}", digits):          # 0241234567
        digits = "+233" + digits[1:]
    elif re.fullmatch(r"233\d{9}", digits):      # 233241234567
        digits = "+" + digits
    elif re.fullmatch(r"[2-5]\d{8}", digits):    # 241234567
        digits = "+233" + digits
    if not re.fullmatch(r"\+\d{8,15}", digits):
        raise HTTPException(422, "Enter a valid phone number, e.g. 0241234567 or +233241234567")
    return digits


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def eta_minutes(distance_km: float) -> int:
    # Straight-line distance at ~36 km/h average. Rough; replace with a
    # road-routing service once we have one.
    return max(5, round(distance_km / 0.6))

"""Runtime configuration, read once from environment variables.

See backend/.env.example for every variable and what it does.
"""

import os
from dataclasses import dataclass, field


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _int(name: str, default: int) -> int:
    raw = _env(name)
    return int(raw) if raw else default


@dataclass(frozen=True)
class Settings:
    env: str = field(default_factory=lambda: _env("BEDALERT_ENV", "dev"))
    database_url: str = field(
        default_factory=lambda: _env("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/bedalert")
    )
    # 'transaction' when DATABASE_URL points at a transaction pooler on a
    # port other than 6543. Pool size per running instance.
    db_pooler: str = field(default_factory=lambda: _env("DB_POOLER"))
    db_pool_max: int = field(default_factory=lambda: _int("DB_POOL_MAX", 10))
    cors_origins: tuple = field(
        default_factory=lambda: tuple(
            o.strip() for o in _env("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()
        )
    )

    # Staff auth = Supabase Auth. Either the project's JWT secret (HS256) or
    # its JWKS URL (asymmetric signing keys) must be set.
    staff_jwt_secret: str = field(default_factory=lambda: _env("SUPABASE_JWT_SECRET"))
    staff_jwks_url: str = field(default_factory=lambda: _env("SUPABASE_JWKS_URL"))
    staff_jwt_audience: str = field(default_factory=lambda: _env("SUPABASE_JWT_AUDIENCE", "authenticated"))

    # Secrets BedAlert owns itself.
    citizen_token_secret: str = field(default_factory=lambda: _env("CITIZEN_TOKEN_SECRET"))
    hash_pepper: str = field(default_factory=lambda: _env("HASH_PEPPER"))
    ussd_callback_secret: str = field(default_factory=lambda: _env("USSD_CALLBACK_SECRET"))

    # SMS provider: 'console' (logs only) or 'africastalking'.
    sms_provider: str = field(default_factory=lambda: _env("SMS_PROVIDER", "console"))
    at_username: str = field(default_factory=lambda: _env("AT_USERNAME"))
    at_api_key: str = field(default_factory=lambda: _env("AT_API_KEY"))
    at_sender_id: str = field(default_factory=lambda: _env("AT_SENDER_ID"))

    # Vercel Cron sends "Authorization: Bearer $CRON_SECRET" to /v1/cron/*.
    cron_secret: str = field(default_factory=lambda: _env("CRON_SECRET"))

    # Business rules.
    stale_after_minutes: int = field(default_factory=lambda: _int("STALE_AFTER_MINUTES", 60))
    hold_minutes_emergency: int = field(default_factory=lambda: _int("HOLD_MINUTES_EMERGENCY", 45))
    hold_minutes_ward: int = field(default_factory=lambda: _int("HOLD_MINUTES_WARD", 120))
    citizen_token_minutes: int = field(default_factory=lambda: _int("CITIZEN_TOKEN_MINUTES", 120))

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"

    def validate(self) -> None:
        """Refuse to start in production with missing or placeholder secrets."""
        if self.is_dev:
            return
        missing = [
            name
            for name, value in (
                ("CITIZEN_TOKEN_SECRET", self.citizen_token_secret),
                ("HASH_PEPPER", self.hash_pepper),
                ("USSD_CALLBACK_SECRET", self.ussd_callback_secret),
            )
            if len(value) < 32
        ]
        if not (self.staff_jwt_secret or self.staff_jwks_url):
            missing.append("SUPABASE_JWT_SECRET or SUPABASE_JWKS_URL")
        if self.sms_provider == "console":
            missing.append("SMS_PROVIDER (console is dev-only)")
        if missing:
            raise RuntimeError("Missing/weak production settings: " + ", ".join(missing))


_DEV_DEFAULTS = {
    "staff_jwt_secret": "dev-staff-jwt-secret-not-for-production-000",
    "citizen_token_secret": "dev-citizen-token-secret-not-for-production",
    "hash_pepper": "dev-hash-pepper-not-for-production-00000000",
    "ussd_callback_secret": "dev-ussd-secret",
}


def load_settings() -> Settings:
    s = Settings()
    if s.is_dev:
        # Fill any unset secret with an obvious dev value so local runs work
        # out of the box. validate() makes sure this never happens in prod.
        overrides = {k: v for k, v in _DEV_DEFAULTS.items() if not getattr(s, k)}
        if overrides:
            s = Settings(**{**s.__dict__, **overrides})
    s.validate()
    return s


settings = load_settings()

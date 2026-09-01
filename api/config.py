"""
Central settings for the api/ package, loaded once from environment
variables and a project-root .env file in dev -- pydantic-settings reads
the .env file itself (env_file below), so this deliberately does NOT reuse
src/generation.py's loader: that module pulls in `anthropic` and the rest
of the RAG pipeline's dependencies at import time, which api/ has no other
reason to depend on. Same intent (project-root .env, dev convenience,
never overriding real environment variables), zero coupling to src/.

Fields with no default are genuinely required in production; Settings()
raises a clear pydantic ValidationError naming every missing one instead of
failing later with a confusing AttributeError the first time a route uses
one, so a misconfigured deployment is caught at process startup.
"""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8", env_prefix="", case_sensitive=True, extra="ignore"
    )

    # -- Database -----------------------------------------------------
    # postgresql+asyncpg://user:password@host:port/dbname
    DATABASE_URL: str

    # -- JWT ------------------------------------------------------------
    JWT_SECRET_KEY: str = Field(min_length=32)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    MFA_TOKEN_EXPIRE_MINUTES: int = 5
    # Comma-separated list of PREVIOUS JWT_SECRET_KEY values, still
    # accepted when VERIFYING a token but never used to SIGN a new one
    # (api/security/jwt.py's decode_token tries JWT_SECRET_KEY first,
    # then each of these in order). Two different procedures, both
    # covered by the same mechanism -- see docs/AUTH_BACKEND_SETUP.md:
    #   - Routine rotation: move the old JWT_SECRET_KEY here during a
    #     grace window (>= ACCESS_TOKEN_EXPIRE_MINUTES) so already-issued
    #     access tokens keep working until they naturally expire, then
    #     remove it once that window has passed.
    #   - Responding to a LEAK: do NOT put the leaked key here -- leave
    #     this empty. Every access token signed with the leaked key
    #     immediately fails to verify. Refresh tokens are unaffected
    #     (they're random opaque values hashed in the database, not
    #     JWTs), so users get a fresh, correctly-signed access token via
    #     POST /auth/refresh without needing to log in again.
    JWT_PREVIOUS_SECRET_KEYS: str = ""

    # -- Password / token hashing ---------------------------------------
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 60
    EMAIL_OTP_EXPIRE_MINUTES: int = 10
    EMAIL_OTP_MAX_ATTEMPTS: int = 5

    # -- RGPD -------------------------------------------------------------
    TERMS_VERSION: str = "2026-01-01"
    ACCOUNT_PURGE_DELAY_DAYS: int = 30
    # Deliberately longer than PASSWORD_RESET_TOKEN_EXPIRE_MINUTES (60):
    # "I want my deleted account back" is a lower-urgency, lower-attack-
    # surface scenario than a password reset, and the user has up to
    # ACCOUNT_PURGE_DELAY_DAYS to notice the email at all -- an hour-long
    # window would expire before most people even check their inbox.
    ACCOUNT_RESTORE_TOKEN_EXPIRE_MINUTES: int = 1440
    # 4.6: how close to the actual purge the "last chance" reminder email
    # goes out (api/tasks/account_deletion_reminder.py) -- separate from
    # the immediate confirmation DELETE /account/me already sends. 3 days
    # gives a real window to notice and restore without being so early
    # it reads as the same email as the immediate confirmation.
    ACCOUNT_DELETION_REMINDER_DAYS_BEFORE: int = 3

    # -- Cookies / CORS -----------------------------------------------------
    FRONTEND_URL: str = "http://localhost:3000"
    COOKIE_DOMAIN: str | None = None
    COOKIE_SECURE: bool = True
    SESSION_MIDDLEWARE_SECRET: str = Field(min_length=32)

    # -- OAuth ------------------------------------------------------------
    GOOGLE_OAUTH_CLIENT_ID: str | None = None
    GOOGLE_OAUTH_CLIENT_SECRET: str | None = None
    GITHUB_OAUTH_CLIENT_ID: str | None = None
    GITHUB_OAUTH_CLIENT_SECRET: str | None = None
    OAUTH_REDIRECT_BASE_URL: str = "http://localhost:8000"

    # -- Transactional email (Resend) --------------------------------------
    RESEND_API_KEY: str | None = None
    EMAIL_FROM_ADDRESS: str = "no-reply@example.com"

    # -- Object storage (S3 or Cloudflare R2, both S3-compatible) -------
    S3_ENDPOINT_URL: str | None = None  # leave unset for real AWS S3
    S3_BUCKET_NAME: str | None = None
    S3_ACCESS_KEY_ID: str | None = None
    S3_SECRET_ACCESS_KEY: str | None = None
    S3_REGION: str = "auto"
    S3_PUBLIC_BASE_URL: str | None = None  # CDN/public URL prefix for uploaded objects

    # -- Celery -------------------------------------------------------------
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # -- Rate limiting (brute-force / spam protection) --------------------
    # Uses its own Redis DB number (2) so its keys never collide with
    # Celery's broker (0) or result backend (1) on the same Redis instance.
    RATE_LIMIT_REDIS_URL: str = "redis://localhost:6379/2"
    # False disables enforcement entirely (every check becomes a no-op,
    # no Redis call at all) -- used by the fast SQLite test suite (see
    # tests/conftest.py) so those tests don't need Redis and can't be
    # accidentally rate-limited by their own repeated calls. Never set
    # this False in a real deployment.
    RATE_LIMIT_ENABLED: bool = True
    LOGIN_RATE_LIMIT_MAX_ATTEMPTS: int = 5
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 900
    REGISTER_RATE_LIMIT_MAX_ATTEMPTS: int = 3
    REGISTER_RATE_LIMIT_WINDOW_SECONDS: int = 3600
    PASSWORD_FORGOT_RATE_LIMIT_MAX_ATTEMPTS: int = 3
    PASSWORD_FORGOT_RATE_LIMIT_WINDOW_SECONDS: int = 3600
    EMAIL_VERIFY_REQUEST_RATE_LIMIT_MAX_ATTEMPTS: int = 3
    EMAIL_VERIFY_REQUEST_RATE_LIMIT_WINDOW_SECONDS: int = 3600
    TWO_FA_VERIFY_RATE_LIMIT_MAX_ATTEMPTS: int = 5
    TWO_FA_VERIFY_RATE_LIMIT_WINDOW_SECONDS: int = 900

    # -- 2FA lockout recovery (lost device AND all recovery codes) --------
    # How long a requested 2FA removal must wait before it can be
    # confirmed -- the same "we'll do this in N hours unless you stop us"
    # pattern GitHub/Google use for the identical scenario, so a
    # compromised mailbox + guessed/leaked password isn't an instant 2FA
    # bypass. The real owner cancels it just by logging in normally in
    # the meantime (see api/routers/two_factor.py's
    # _cancel_pending_lockout_recovery).
    TWO_FA_LOCKOUT_RECOVERY_DELAY_HOURS: int = 24
    # Total link validity from the moment it's requested -- must be
    # comfortably longer than the delay above, so there's a real window
    # to actually click "confirm" once eligible, not just the instant it
    # becomes valid.
    TWO_FA_LOCKOUT_RECOVERY_TOKEN_EXPIRE_HOURS: int = 96
    ACCOUNT_RESTORE_RATE_LIMIT_MAX_ATTEMPTS: int = 3
    ACCOUNT_RESTORE_RATE_LIMIT_WINDOW_SECONDS: int = 3600

    @field_validator("DATABASE_URL")
    @classmethod
    def _require_asyncpg_driver(cls, value):
        if value.startswith("postgresql://"):
            raise ValueError(
                "DATABASE_URL must use the asyncpg driver: "
                "postgresql+asyncpg://... (got a plain postgresql:// URL)"
            )
        return value


settings = Settings()

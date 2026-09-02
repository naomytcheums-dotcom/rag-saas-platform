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

from pydantic import Field, field_validator, model_validator
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
    # RGPD Art. 12: a data subject must be able to easily reach the
    # controller to exercise their rights or ask questions. Required (no
    # default) rather than silently omitting the footer or shipping a
    # fake address nobody reads -- api/services/email.py's _send()
    # appends it to every single email this app sends, unconditionally.
    SUPPORT_EMAIL: str

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

    # -- Session lifecycle (audit Categorie 1, items 13/14/17) -------------
    # An access token's paired Session row (api/models/session.py) is
    # revoked -- and its access token blacklisted, same as any other
    # revocation -- if this many minutes pass with no authenticated
    # request touching it. Independent of the session's own absolute
    # expiry (REFRESH_TOKEN_EXPIRE_DAYS above): idle timeout catches a
    # forgotten-but-not-stolen session; absolute expiry is the hard
    # ceiling regardless of activity.
    SESSION_IDLE_TIMEOUT_MINUTES: int = 30
    # How many sessions (devices/browsers) a single account may have
    # active at once. Enforced at issuance (api/security/sessions.py's
    # issue_session()): the OLDEST active session is revoked to make
    # room for a new one, rather than rejecting the new login outright
    # -- a new login is always the one thing a real owner is doing right
    # now; an old, possibly-forgotten session is the more likely one to
    # be stale or someone else's.
    MAX_CONCURRENT_SESSIONS: int = 5

    # -- Password policy (audit Categorie 1, items 15/16) ------------------
    # How many of a user's most recent passwords (api/models/password_history.py)
    # a new password is checked against, in addition to the CURRENT one.
    PASSWORD_HISTORY_SIZE: int = 5
    # api/security/password_similarity.py's Levenshtein-distance check
    # against the user's own email/name -- a password within this many
    # single-character edits of either is rejected. 3 catches trivial
    # cases ("janedoe" vs "janedoe1") without being so aggressive it
    # rejects a password that only coincidentally shares a few letters.
    PASSWORD_SIMILARITY_MIN_DISTANCE: int = 3

    # -- Audit log (audit Categorie 2, items 18-21) -------------------------
    # A dedicated key for api/security/audit_log.py's hash-chain checksum
    # -- deliberately NOT reusing JWT_SECRET_KEY or SESSION_MIDDLEWARE_SECRET
    # (key separation: rotating either of those for its own reason must
    # never retroactively change what every past audit row's checksum
    # was computed with). Required, no default, same reasoning as
    # JWT_SECRET_KEY -- an audit log without real tamper-evidence isn't
    # the feature this was asked to build.
    AUDIT_LOG_HMAC_SECRET_KEY: str = Field(min_length=32)

    # Slack-compatible incoming-webhook URL ({"text": "..."} POST body)
    # for real-time security alerts (item 21) -- unset disables webhook
    # alerting entirely, same "optional integration" pattern as
    # GOOGLE_OAUTH_CLIENT_ID. A dedicated email address alerts go to as
    # well/instead (api/services/email.py's send_security_alert_email) --
    # either, both, or neither may be configured.
    SECURITY_ALERT_WEBHOOK_URL: str | None = None
    SECURITY_ALERT_EMAIL: str | None = None
    # A spike of this many failed logins (by IP OR by targeted email)
    # within SECURITY_ALERT_WINDOW_MINUTES triggers one alert -- see
    # api/services/security_alerts.py's check_and_alert_on_failed_login_spike.
    SECURITY_ALERT_FAILED_LOGIN_THRESHOLD: int = 10
    SECURITY_ALERT_WINDOW_MINUTES: int = 5

    # -- Geo-adaptive rate limiting (audit Categorie 4, item 29) -----------
    # api/security/geoip.py resolves a caller's IP to an ISO 3166-1
    # alpha-2 country code (ipapi.co, no API key needed), cached in Redis
    # so a brute-force burst from one IP doesn't turn into one outbound
    # HTTP call per attempt. api/security/adaptive_rate_limit.py then
    # scales LOGIN_RATE_LIMIT_MAX_ATTEMPTS / REGISTER_RATE_LIMIT_MAX_ATTEMPTS
    # by GEO_RATE_LIMIT_TRUSTED_MULTIPLIER or _SUSPICIOUS_MULTIPLIER when
    # that country appears in TRUSTED_COUNTRIES / SUSPICIOUS_COUNTRIES.
    # Both lists empty (the default) means every caller gets the flat,
    # unadjusted limit -- identical behavior to before this feature existed.
    GEO_IP_LOOKUP_ENABLED: bool = True
    GEO_IP_API_URL: str = "https://ipapi.co/{ip}/country/"
    GEO_IP_LOOKUP_TIMEOUT_SECONDS: float = 2.0
    GEO_IP_CACHE_TTL_SECONDS: int = 3600
    TRUSTED_COUNTRIES: str = ""
    SUSPICIOUS_COUNTRIES: str = ""
    GEO_RATE_LIMIT_TRUSTED_MULTIPLIER: float = 2.0
    GEO_RATE_LIMIT_SUSPICIOUS_MULTIPLIER: float = 0.5

    # -- Trusted IP / VPN exemption (audit Categorie 4, item 30) -----------
    # Comma-separated individual IPs and/or CIDR ranges (e.g.
    # "203.0.113.5,10.8.0.0/24") fully exempted from rate limiting by
    # api/security/adaptive_rate_limit.py -- for known-safe sources
    # (internal tooling, a company VPN egress IP, a monitoring/synthetic
    # check) that would otherwise share the same brute-force limits as an
    # anonymous public caller. Empty (the default) exempts nothing.
    TRUSTED_IPS: str = ""

    # -- Shared encryption-at-rest for DB-stored secrets --------------------
    # A Fernet key (symmetric, authenticated encryption) protecting the
    # two Categorie-4 secrets that must live in Postgres rather than a
    # .env file, because their whole point is to change WITHOUT a
    # redeploy: JWT signing keys (item 28) and enterprise SSO client
    # secrets (item 27) -- see api/security/secret_encryption.py. Only
    # required once one of those features is actually used (creating the
    # first JWTSigningKey row, or the first EnterpriseSSOConnection);
    # unset otherwise. Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    SECRET_ENCRYPTION_KEY: str | None = None

    # -- Automatic JWT key rotation (audit Categorie 4, item 28) -----------
    # Complements the manual JWT_PREVIOUS_SECRET_KEYS mechanism above with
    # a DB-backed key (api/models/jwt_signing_key.py) that a Celery Beat
    # task (api/tasks/jwt_key_rotation.py) rotates on its own schedule --
    # see that task's docstring for exactly how "automatic" is achieved
    # without a redeploy. 0 (the default) disables automatic rotation
    # entirely; the existing manual env-var mechanism keeps working
    # unchanged either way.
    JWT_AUTO_ROTATION_INTERVAL_DAYS: int = 0
    # How long a retired DB-backed key remains valid for VERIFYING an
    # already-issued token after a rotation -- must comfortably exceed
    # REFRESH_TOKEN_EXPIRE_DAYS's effective access-token lifetime window
    # (a session can go REFRESH_TOKEN_EXPIRE_DAYS between refreshes, and
    # each refresh mints an access token good for ACCESS_TOKEN_EXPIRE_MINUTES
    # more) so a token signed just before a rotation never outlives the
    # key that can still verify it.
    JWT_KEY_RETENTION_DAYS: int = 7
    # How often a running API process re-reads the DB-backed signing key
    # table (api/security/jwt.py's in-memory cache) -- this, not a
    # restart, is what makes a Celery-driven rotation "automatic" for
    # every already-running worker process, single or multi.
    JWT_KEY_CACHE_REFRESH_SECONDS: int = 60
    JWT_KEY_ROTATION_ADMIN_EMAIL: str | None = None

    # -- WebAuthn / FIDO2 (audit Categorie 4, item 26) ---------------------
    # rp_id must be the exact domain (no scheme/port) the frontend is
    # served from -- a WebAuthn credential is cryptographically bound to
    # it and simply won't work if this doesn't match. rp_origin is the
    # full origin (with scheme) the browser's navigator.credentials calls
    # actually run from; the two are independently configurable since a
    # dev setup commonly runs the frontend on a different port than "the
    # domain" (e.g. rp_id=localhost, rp_origin=http://localhost:3000).
    WEBAUTHN_RP_ID: str = "localhost"
    WEBAUTHN_RP_NAME: str = "RAG SaaS Platform"
    WEBAUTHN_RP_ORIGIN: str = "http://localhost:3000"
    WEBAUTHN_MAX_CREDENTIALS_PER_USER: int = 10

    # -- Enterprise SSO / OIDC (audit Categorie 4, item 27) -----------------
    # Each EnterpriseSSOConnection.client_secret (a third-party IdP's
    # secret, admin-configured via POST /admin/sso/connections) is
    # encrypted at rest using SECRET_ENCRYPTION_KEY above.

    @field_validator("DATABASE_URL")
    @classmethod
    def _require_asyncpg_driver(cls, value):
        if value.startswith("postgresql://"):
            raise ValueError(
                "DATABASE_URL must use the asyncpg driver: "
                "postgresql+asyncpg://... (got a plain postgresql:// URL)"
            )
        return value

    @model_validator(mode="after")
    def _deletion_reminder_must_fire_before_the_purge(self) -> "Settings":
        """A misconfiguration where ACCOUNT_DELETION_REMINDER_DAYS_BEFORE
        >= ACCOUNT_PURGE_DELAY_DAYS would make the pre-purge reminder
        (api/tasks/account_deletion_reminder.py) eligible the moment
        deletion is requested -- functionally a duplicate of the
        immediate confirmation email DELETE /account/me already sends,
        defeating the entire point of a SECOND, later warning (4.6).
        Caught here, at startup, rather than discovered as "why did this
        user get two identical-looking emails the same day.\""""
        if self.ACCOUNT_DELETION_REMINDER_DAYS_BEFORE >= self.ACCOUNT_PURGE_DELAY_DAYS:
            raise ValueError(
                "ACCOUNT_DELETION_REMINDER_DAYS_BEFORE "
                f"({self.ACCOUNT_DELETION_REMINDER_DAYS_BEFORE}) must be less than "
                f"ACCOUNT_PURGE_DELAY_DAYS ({self.ACCOUNT_PURGE_DELAY_DAYS}) -- the reminder is "
                "meant to fire partway through the grace window, not immediately."
            )
        return self

    @model_validator(mode="after")
    def _restore_token_must_expire_before_the_purge(self) -> "Settings":
        """5.7 audit finding: api/routers/account.py's confirm_account_restore
        checks the restore TOKEN's own expiry, not deletion_scheduled_at,
        so it relies on this ordering to stay safe -- a restore token that
        could still be valid AFTER api/tasks/account_purge.py has already
        hard-deleted the row would just fail harmlessly (cascade delete
        takes the token row down with the user, see
        tests/test_postgres_integration.py), but only by accident. Caught
        here, at startup, so that safety never depends on a coincidence
        two independently-configured durations happen to preserve."""
        purge_delay_minutes = self.ACCOUNT_PURGE_DELAY_DAYS * 24 * 60
        if self.ACCOUNT_RESTORE_TOKEN_EXPIRE_MINUTES >= purge_delay_minutes:
            raise ValueError(
                "ACCOUNT_RESTORE_TOKEN_EXPIRE_MINUTES "
                f"({self.ACCOUNT_RESTORE_TOKEN_EXPIRE_MINUTES}) must be less than "
                f"ACCOUNT_PURGE_DELAY_DAYS converted to minutes ({purge_delay_minutes}) -- "
                "a restore link must not still be valid after the account it points to "
                "could already have been permanently purged."
            )
        return self


settings = Settings()

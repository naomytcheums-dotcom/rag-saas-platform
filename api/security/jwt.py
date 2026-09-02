"""
Short-lived access tokens (1.1.8) plus a narrowly-scoped "mfa pending"
token used only to bridge POST /auth/login -> POST /auth/2fa/verify-login
when 2FA is enabled (1.1.7), so that second step doesn't need the password
again yet also can't be used as a real access token (`purpose` claim is
checked, not just presence of a valid signature).

1.1.15: every token also carries a `jti` (a fresh random id). For an
access token, api/security/sessions.py's issue_session() stores that same
jti on the Session row it's paired with, and api/dependencies.py's
get_current_user checks it against the blacklist (api/models/revoked_token.py)
on every request -- what actually makes an access token revocable despite
still being a self-contained, signature-verified JWT. MFA-pending tokens
get a jti too (every token does, for a uniform claim shape) but it's never
tracked in the blacklist; they're single-purpose, already rate-limited at
the endpoints that consume them, and short-lived enough that revocability
isn't worth the extra bookkeeping.

1.1.15 key rotation: decode_token() verifies against JWT_SECRET_KEY first,
then falls back through JWT_PREVIOUS_SECRET_KEYS in order -- see that
setting's docstring in api/config.py for the two different rotation
procedures this supports (routine rotation vs. responding to a leak).

Audit finding 28 -- automatic rotation. The manual mechanism above stays
exactly as it was (a deployment can use ONLY it, forever, unchanged); on
top of it, this module ALSO tries any DB-backed keys
(api/models/jwt_signing_key.py) held in the in-memory cache below.
refresh_jwt_key_cache() populates that cache from Postgres; it's called
once at API startup and then on a JWT_KEY_CACHE_REFRESH_SECONDS timer
(api/main.py's lifespan) -- THAT timer, not a process restart, is what
lets api/tasks/jwt_key_rotation.py's Celery Beat task rotate the signing
key "automatically": every already-running API process (single or
multi-worker) independently notices the change from Postgres within at
most JWT_KEY_CACHE_REFRESH_SECONDS. create_access_token/decode_token
themselves stay perfectly synchronous either way -- they only ever read
this plain in-memory dict, never touch the database on the request path.
"""

import datetime as dt
import logging
import uuid
from dataclasses import dataclass
from enum import StrEnum

import jwt
from jwt import ExpiredSignatureError, InvalidSignatureError, InvalidTokenError
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings

logger = logging.getLogger(__name__)


class TokenPurpose(StrEnum):
    ACCESS = "access"
    MFA_PENDING = "mfa_pending"


class InvalidTokenPurposeError(Exception):
    pass


@dataclass(frozen=True)
class DecodedToken:
    """What decode_token() below hands back: user_id for the obvious
    reason, jti so api/dependencies.py's get_current_user can check THIS
    exact access token against the revocation blacklist."""

    user_id: uuid.UUID
    jti: str


# Populated by refresh_jwt_key_cache() below -- empty (the default state
# for every process until its first successful refresh) means "no
# DB-backed keys exist/known yet," under which _signing_key() and
# _verification_keys() below behave EXACTLY like the pre-1.1.15/28 code:
# sign and verify with JWT_SECRET_KEY + JWT_PREVIOUS_SECRET_KEYS only.
_key_cache: dict = {"active_secret": None, "verification_secrets": []}


def _signing_key() -> str:
    """The key used to sign a brand-new token: the DB-backed active key
    once refresh_jwt_key_cache() has found one, else JWT_SECRET_KEY
    unchanged -- so a deployment that never enables
    JWT_AUTO_ROTATION_INTERVAL_DAYS (0 by default) signs tokens exactly
    as it did before this feature existed."""
    return _key_cache["active_secret"] or settings.JWT_SECRET_KEY


def _verification_keys() -> list[str]:
    """Every key a still-valid token might have been signed with, tried
    in the order most likely to succeed first: the cached DB-backed
    active key, then any DB-backed keys still within their retention
    window after being retired by a rotation (see refresh_jwt_key_cache),
    then JWT_SECRET_KEY (env) and JWT_PREVIOUS_SECRET_KEYS (env) -- the
    original manual mechanism, always tried too and unconditionally, so
    automatic and manual rotation can both be in play at once (e.g.
    mid-migration from one to the other) without either interfering with
    the other."""
    keys = list(_key_cache["verification_secrets"])
    keys.append(settings.JWT_SECRET_KEY)
    keys.extend(k.strip() for k in settings.JWT_PREVIOUS_SECRET_KEYS.split(",") if k.strip())
    return keys


async def refresh_jwt_key_cache(db: AsyncSession) -> None:
    """
    Reloads this module's in-memory key cache from the jwt_signing_keys
    table -- see this module's top docstring for who calls this and why
    that's what makes rotation "automatic" without a redeploy.

    Selects the active key (if any) plus every retired key still inside
    JWT_KEY_RETENTION_DAYS of its retirement -- a token signed by a key
    retired longer ago than that is expected to have already naturally
    expired (see JWT_KEY_RETENTION_DAYS's own docstring in api/config.py
    for the ordering guarantee this relies on), so excluding it here
    keeps the cache (and thus every decode_token() signature-check loop)
    from growing without bound over the lifetime of a deployment.

    A DB error or a bad decryption (SECRET_ENCRYPTION_KEY missing/wrong)
    logs a warning and leaves the EXISTING cache untouched, never
    cleared -- a transient Postgres blip or a startup-ordering hiccup
    must not suddenly make this process unable to verify tokens it could
    verify a moment ago.
    """
    from api.models.jwt_signing_key import JWTSigningKey  # local import: keeps this module DB-model-free at import time, matching its pre-1.1.15/28 zero-SQLAlchemy-import shape for every caller that never touches rotation
    from api.security.secret_encryption import decrypt_secret

    try:
        retention_cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=settings.JWT_KEY_RETENTION_DAYS)
        rows = (await db.scalars(
            select(JWTSigningKey)
            .where(or_(JWTSigningKey.is_active.is_(True), JWTSigningKey.retired_at > retention_cutoff))
            .order_by(JWTSigningKey.is_active.desc(), JWTSigningKey.created_at.desc())
        )).all()

        active_secret = None
        verification_secrets = []
        for row in rows:
            secret = decrypt_secret(row.secret)
            verification_secrets.append(secret)
            if row.is_active:
                active_secret = secret

        _key_cache["active_secret"] = active_secret
        _key_cache["verification_secrets"] = verification_secrets
    except Exception as exc:  # noqa: BLE001 -- see docstring: must never crash a request-serving process's startup/background timer
        logger.warning("failed to refresh the JWT signing-key cache, keeping the existing one: %s", exc)


def _create_token(subject: uuid.UUID, purpose: TokenPurpose, expires_delta: dt.timedelta) -> tuple[str, str]:
    """Shared builder behind create_access_token/create_mfa_pending_token
    below -- every token this app issues carries `sub` (the user id),
    `jti` (this module's top docstring), `purpose` (checked by
    decode_token), `iat`/`exp`, signed with the app's CURRENT
    JWT_SECRET_KEY (never a previous one -- those are for verifying
    already-issued tokens only, see _verification_keys()). Returns
    (encoded_token, jti): callers that mint a real access token need the
    jti to store alongside the Session row it's paired with."""
    now = dt.datetime.now(dt.timezone.utc)
    jti = str(uuid.uuid4())
    payload = {
        "sub": str(subject),
        "jti": jti,
        "purpose": purpose.value,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, _signing_key(), algorithm=settings.JWT_ALGORITHM), jti


def create_access_token(user_id: uuid.UUID) -> tuple[str, str]:
    """The token a client sends as `Authorization: Bearer <token>` on
    every authenticated request. Short-lived (ACCESS_TOKEN_EXPIRE_MINUTES,
    15 by default) on purpose, AND now revocable before that expiry via
    the blacklist (this module's top docstring) -- the short lifetime
    still matters as the fallback: a token that's leaked but never
    detected/revoked is only ever useful for at most 15 minutes. Returns
    (token, jti) -- see api/security/sessions.py's issue_session() for
    why the caller needs the jti."""
    return _create_token(user_id, TokenPurpose.ACCESS, dt.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))


def create_mfa_pending_token(user_id: uuid.UUID) -> str:
    """A short-lived ticket proving "this user's password just checked
    out" without being a real access token -- see this module's top
    docstring and api/routers/two_factor.py's verify_two_factor_login()."""
    token, _jti = _create_token(user_id, TokenPurpose.MFA_PENDING, dt.timedelta(minutes=settings.MFA_TOKEN_EXPIRE_MINUTES))
    return token


def _decode_payload(token: str) -> dict:
    """Tries each configured verification key in turn, moving to the
    next ONLY on a signature mismatch -- any other failure (expired,
    malformed) means the right key was already found and the problem is
    real, so it's raised immediately rather than masked by trying more
    keys (which wouldn't fix an expiry problem anyway)."""
    last_error: Exception = InvalidSignatureError("token signature does not match any configured key")
    for key in _verification_keys():
        try:
            return jwt.decode(token, key, algorithms=[settings.JWT_ALGORITHM])
        except InvalidSignatureError as exc:
            last_error = exc
            continue
    raise last_error


def decode_token(token: str, expected_purpose: TokenPurpose) -> DecodedToken:
    """Raises ExpiredSignatureError / InvalidTokenError (jwt's own
    exceptions, already carrying a clear message) on a bad signature or
    expiry, and InvalidTokenPurposeError if the token is otherwise valid
    but was issued for a different purpose -- e.g. an mfa_pending token
    presented where a real access token is required."""
    payload = _decode_payload(token)
    if payload.get("purpose") != expected_purpose.value:
        raise InvalidTokenPurposeError(f"expected a '{expected_purpose.value}' token, got '{payload.get('purpose')}'")
    return DecodedToken(user_id=uuid.UUID(payload["sub"]), jti=payload["jti"])


__all__ = [
    "TokenPurpose",
    "InvalidTokenPurposeError",
    "DecodedToken",
    "ExpiredSignatureError",
    "InvalidTokenError",
    "create_access_token",
    "create_mfa_pending_token",
    "decode_token",
    "refresh_jwt_key_cache",
]

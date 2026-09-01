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
"""

import datetime as dt
import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import jwt
from jwt import ExpiredSignatureError, InvalidSignatureError, InvalidTokenError

from api.config import settings


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


def _verification_keys() -> list[str]:
    """The current signing key, plus any keys listed in
    JWT_PREVIOUS_SECRET_KEYS -- tried in that order by decode_token()."""
    keys = [settings.JWT_SECRET_KEY]
    keys.extend(k.strip() for k in settings.JWT_PREVIOUS_SECRET_KEYS.split(",") if k.strip())
    return keys


def _create_token(
    subject: uuid.UUID, purpose: TokenPurpose, expires_delta: dt.timedelta, extra_claims: dict[str, Any] | None = None
) -> tuple[str, str]:
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
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM), jti


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
]

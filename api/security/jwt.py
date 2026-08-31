"""
Short-lived, stateless access tokens (1.1.8) plus a narrowly-scoped "mfa
pending" token used only to bridge POST /auth/login -> POST /auth/2fa/verify-login
when 2FA is enabled (1.1.7), so that second step doesn't need the password
again yet also can't be used as a real access token (`purpose` claim is
checked, not just presence of a valid signature).
"""

import datetime as dt
import uuid
from enum import StrEnum
from typing import Any

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from api.config import settings


class TokenPurpose(StrEnum):
    ACCESS = "access"
    MFA_PENDING = "mfa_pending"


class InvalidTokenPurposeError(Exception):
    pass


def _create_token(subject: uuid.UUID, purpose: TokenPurpose, expires_delta: dt.timedelta, extra_claims: dict[str, Any] | None = None) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": str(subject),
        "purpose": purpose.value,
        "iat": now,
        "exp": now + expires_delta,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: uuid.UUID) -> str:
    return _create_token(
        user_id, TokenPurpose.ACCESS, dt.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )


def create_mfa_pending_token(user_id: uuid.UUID) -> str:
    return _create_token(
        user_id, TokenPurpose.MFA_PENDING, dt.timedelta(minutes=settings.MFA_TOKEN_EXPIRE_MINUTES)
    )


def decode_token(token: str, expected_purpose: TokenPurpose) -> uuid.UUID:
    """Raises ExpiredSignatureError / InvalidTokenError (jwt's own
    exceptions, already carrying a clear message) on a bad signature or
    expiry, and InvalidTokenPurposeError if the token is otherwise valid
    but was issued for a different purpose -- e.g. an mfa_pending token
    presented where a real access token is required."""
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    if payload.get("purpose") != expected_purpose.value:
        raise InvalidTokenPurposeError(f"expected a '{expected_purpose.value}' token, got '{payload.get('purpose')}'")
    return uuid.UUID(payload["sub"])


__all__ = [
    "TokenPurpose",
    "InvalidTokenPurposeError",
    "ExpiredSignatureError",
    "InvalidTokenError",
    "create_access_token",
    "create_mfa_pending_token",
    "decode_token",
]

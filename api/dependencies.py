"""Shared FastAPI dependencies: DB session (re-exported for convenience) and
the current-user resolver every protected route depends on."""

import uuid

from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import ExpiredSignatureError, InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models.user import User
from api.security.jwt import InvalidTokenPurposeError, TokenPurpose, decode_token

__all__ = ["get_db", "get_current_user", "get_refresh_token"]

_bearer_scheme = HTTPBearer(description="Access token from POST /auth/login or /auth/refresh")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency used by every protected route (`Depends(get_current_user)`
    in a route's signature): reads the `Authorization: Bearer <token>`
    header via the HTTPBearer scheme above, decodes it as an access-purpose
    JWT, and loads the matching user row. Any failure along the way --
    missing header, malformed/expired token, or a user that no longer
    exists/is deactivated/soft-deleted -- collapses to the same generic
    401, so a caller can't distinguish "your token is fine but your
    account was deleted" from "your token is garbage."
    """
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token")

    try:
        user_id: uuid.UUID = decode_token(credentials.credentials, TokenPurpose.ACCESS)
    except (ExpiredSignatureError, InvalidTokenError, InvalidTokenPurposeError):
        raise unauthorized

    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active or user.is_deleted:
        raise unauthorized
    return user


def get_refresh_token(refresh_token: str | None = Cookie(default=None)) -> str:
    """1.1.8 -- the refresh token travels as an httpOnly cookie, never in a
    JSON body, so it's unreachable from JS even if an XSS bug slips through
    elsewhere on the page."""
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token cookie present")
    return refresh_token

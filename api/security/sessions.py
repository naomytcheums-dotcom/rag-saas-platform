"""
Shared session issuance/rotation/revocation logic (1.1.8, 1.1.9), used by
every router that can end with a logged-in user: auth.py (register/login),
oauth.py (OAuth callbacks), two_factor.py (the post-MFA login step).

Kept out of auth.py itself so oauth.py and two_factor.py don't have to
import "auth" to get it -- this is genuinely shared infrastructure, not
auth.py's private implementation detail.
"""

import datetime as dt
import uuid

from fastapi import Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.session import Session
from api.schemas.auth import TokenResponse
from api.security.hashing import generate_raw_token, hash_token
from api.security.jwt import create_access_token

REFRESH_COOKIE_NAME = "refresh_token"
# "/" rather than "/auth": GET/DELETE /sessions (1.1.9, a different router)
# also needs to read this cookie to tell which session is the caller's own
# (`is_current` in api/routers/sessions.py) -- cookie path scoping is
# browser/client-enforced, so a narrower path here would silently make
# that comparison always fail outside of /auth/* routes. httpOnly+Secure+
# SameSite=lax are what actually protect this cookie; the path is not a
# meaningful second layer once more than one router needs it.
REFRESH_COOKIE_PATH = "/"


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def set_refresh_cookie(response: Response, raw_refresh_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path=REFRESH_COOKIE_PATH,
        domain=settings.COOKIE_DOMAIN,
        secure=settings.COOKIE_SECURE,
        httponly=True,
        samesite="lax",
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH, domain=settings.COOKIE_DOMAIN
    )


async def issue_session(db: AsyncSession, response: Response, request: Request, user_id: uuid.UUID) -> TokenResponse:
    """Creates a new Session row (a fresh refresh token) and sets it as an
    httpOnly cookie; returns the access token for the JSON response body."""
    raw_refresh_token = generate_raw_token()
    now = dt.datetime.now(dt.timezone.utc)

    session = Session(
        user_id=user_id,
        refresh_token_hash=hash_token(raw_refresh_token),
        device_info=request.headers.get("user-agent"),
        ip_address=_client_ip(request),
        expires_at=now + dt.timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(session)
    await db.flush()

    set_refresh_cookie(response, raw_refresh_token)
    return TokenResponse(
        access_token=create_access_token(user_id),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def get_active_session_by_raw_token(db: AsyncSession, raw_refresh_token: str) -> Session | None:
    session = await db.scalar(select(Session).where(Session.refresh_token_hash == hash_token(raw_refresh_token)))
    if session is None or not session.is_active:
        return None
    return session


async def revoke_session(db: AsyncSession, session: Session) -> None:
    session.revoked_at = dt.datetime.now(dt.timezone.utc)
    await db.flush()

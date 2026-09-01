"""
Core authentication endpoints: 1.1.1 register, 1.1.2 login/logout,
1.1.8 refresh. Every other auth router (password.py, verify.py, oauth.py,
two_factor.py, sessions.py) builds on the session/token machinery defined
here and in api/security/sessions.py.

How the token model works, in plain terms:
- A successful login/register/refresh returns a short-lived "access
  token" (a JWT, expires in ACCESS_TOKEN_EXPIRE_MINUTES) in the JSON
  response body. The frontend keeps this in memory and sends it as
  `Authorization: Bearer <token>` on every request that needs auth.
- At the same time, a long-lived "refresh token" is set as an httpOnly
  cookie (invisible to JavaScript, sent automatically by the browser).
  When the access token expires, the frontend calls POST /auth/refresh,
  which reads that cookie and issues a brand new access token + a brand
  new refresh token (the old one is immediately revoked -- see the
  comment on /refresh below for why).
"""

import datetime as dt
import logging

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.dependencies import get_db
from api.models.user import User
from api.schemas.auth import LoginRequest, MessageResponse, MFARequiredResponse, RegisterRequest, TokenResponse
from api.security.hashing import hash_password, verify_password
from api.security.sessions import (
    clear_refresh_cookie,
    get_active_session_by_raw_token,
    issue_session,
    revoke_session,
)
from api.security.jwt import create_mfa_pending_token
from api.services.verification import create_and_send_email_otp

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

# Reused for every login failure so the client never learns *which* part
# was wrong (unknown email vs. wrong password) -- see the comment inside
# login() for the reasoning.
_GENERIC_LOGIN_ERROR = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """
    Create a new account and log the user in immediately (the response
    already contains a working access token + refresh cookie -- there is
    no separate "please verify your email before you can do anything"
    gate). A verification code is emailed in the background regardless;
    see api/routers/verify.py for how the user later confirms it.

    Body: RegisterRequest (email, password, optional full_name/company,
    and accept_terms which Pydantic itself rejects if False -- see
    api/schemas/auth.py).
    """
    existing = await db.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        # Deliberately vague: confirming "this email is already registered"
        # to an anonymous caller is a user-enumeration leak.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Could not register with these details")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        company=payload.company,
        # 1.1.12 RGPD consent: recorded once, here, at the moment the user
        # actually agreed -- never edited afterwards, so it stays an
        # honest record of what was agreed to and when.
        consent_given_at=dt.datetime.now(dt.timezone.utc),
        terms_version=settings.TERMS_VERSION,
    )
    db.add(user)
    await db.flush()  # assigns user.id without committing yet -- needed below before the row is final

    await create_and_send_email_otp(db, user)  # 1.1.4 -- fire-and-forget-ish: logs a warning and continues on email failure, never blocks registration
    tokens = await issue_session(db, response, request, user.id)
    await db.commit()
    return tokens


@router.post("/login", response_model=None)
async def login(payload: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> TokenResponse | MFARequiredResponse:
    """
    Password login. Returns one of two shapes depending on whether the
    account has 2FA enabled:
    - TokenResponse: normal case, access token + refresh cookie, done.
    - MFARequiredResponse: the password was correct but the account has
      TOTP enabled (see api/routers/two_factor.py) -- the frontend must
      then call POST /auth/2fa/verify-login with the returned mfa_token
      and a 6-digit code before it gets real tokens. This second call is
      the only place tokens are actually issued for a 2FA account.
    """
    user = await db.scalar(select(User).where(User.email == payload.email))
    # Every one of these three distinct failure reasons -- unknown email,
    # OAuth-only account with no password set, wrong password -- raises
    # the exact same generic error. Returning a different message for
    # "that email doesn't exist" vs "wrong password" would let an
    # attacker enumerate which emails are registered one guess at a time.
    if user is None or user.hashed_password is None or not verify_password(payload.password, user.hashed_password):
        raise _GENERIC_LOGIN_ERROR
    if not user.is_active or user.is_deleted:
        raise _GENERIC_LOGIN_ERROR

    if user.totp_enabled:
        return MFARequiredResponse(mfa_token=create_mfa_pending_token(user.id))

    tokens = await issue_session(db, response, request, user.id)
    await db.commit()
    return tokens


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Exchange the httpOnly refresh cookie for a brand new access token
    (and a brand new refresh cookie -- rotation, see below). The frontend
    calls this whenever an access token expires (every
    ACCESS_TOKEN_EXPIRE_MINUTES) rather than asking the user to log in
    again every 15 minutes.
    """
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token, please log in again")
    if not refresh_token:
        raise unauthorized

    session = await get_active_session_by_raw_token(db, refresh_token)
    if session is None:
        clear_refresh_cookie(response)
        raise unauthorized

    user = await db.get(User, session.user_id)
    if user is None or not user.is_active or user.is_deleted:
        clear_refresh_cookie(response)
        raise unauthorized

    # Rotation (1.1.8): the consumed refresh token is revoked, not reused --
    # a stolen-then-replayed old token fails the is_active check on its
    # second use instead of silently working forever.
    await revoke_session(db, session)
    tokens = await issue_session(db, response, request, user.id)
    await db.commit()
    return tokens


@router.post("/logout", response_model=MessageResponse)
async def logout(response: Response, refresh_token: str | None = Cookie(default=None), db: AsyncSession = Depends(get_db)):
    """
    Ends the current session: revokes the refresh token server-side (so
    it can never be used again, even if someone captured a copy of the
    cookie before this call) and clears the cookie in the browser.
    Tolerant of being called with no cookie at all -- logging out twice,
    or logging out after the session already expired, is not an error.
    """
    if refresh_token:
        session = await get_active_session_by_raw_token(db, refresh_token)
        if session is not None:
            await revoke_session(db, session)
            await db.commit()
    clear_refresh_cookie(response)
    return MessageResponse(message="Logged out")

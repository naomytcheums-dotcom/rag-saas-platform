"""1.1.1 register, 1.1.2 login/logout, 1.1.8 refresh -- the core auth loop."""

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

_GENERIC_LOGIN_ERROR = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
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
        consent_given_at=dt.datetime.now(dt.timezone.utc),
        terms_version=settings.TERMS_VERSION,
    )
    db.add(user)
    await db.flush()

    await create_and_send_email_otp(db, user)
    tokens = await issue_session(db, response, request, user.id)
    await db.commit()
    return tokens


@router.post("/login", response_model=None)
async def login(payload: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> TokenResponse | MFARequiredResponse:
    user = await db.scalar(select(User).where(User.email == payload.email))
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
    if refresh_token:
        session = await get_active_session_by_raw_token(db, refresh_token)
        if session is not None:
            await revoke_session(db, session)
            await db.commit()
    clear_refresh_cookie(response)
    return MessageResponse(message="Logged out")

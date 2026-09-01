"""1.1.4 -- email verification via a 6-digit OTP."""

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.dependencies import get_current_user, get_db
from api.models.token import EmailVerificationToken
from api.models.user import User
from api.schemas.auth import EmailVerifyConfirmRequest, MessageResponse
from api.security.hashing import hash_token
from api.security.rate_limit import enforce_rate_limit
from api.services.verification import create_and_send_email_otp
from api.utils import as_aware_utc

router = APIRouter(prefix="/auth/verify-email", tags=["auth"])


@router.post("/request", response_model=MessageResponse)
async def request_verification_code(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Sends a fresh 6-digit code by email (a new row every call -- old,
    unused codes are simply superseded since /confirm below always
    checks the most recent one). Used both right after registration if
    the first email never arrived, and any time later if the user wants
    to (re-)verify. Rate-limited by email so repeatedly requesting a
    fresh code can't be used to spam the account owner's inbox.
    """
    await enforce_rate_limit(
        f"ratelimit:verify-email:email:{current_user.email}",
        settings.EMAIL_VERIFY_REQUEST_RATE_LIMIT_MAX_ATTEMPTS, settings.EMAIL_VERIFY_REQUEST_RATE_LIMIT_WINDOW_SECONDS,
    )

    if current_user.is_email_verified:
        return MessageResponse(message="Email is already verified")
    await create_and_send_email_otp(db, current_user)
    await db.commit()
    return MessageResponse(message="Verification code sent")


@router.post("/confirm", response_model=MessageResponse)
async def confirm_verification_code(
    payload: EmailVerifyConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Checks the 6-digit code the user typed in against the most recent
    unused code emailed to them. Three ways this can fail besides a
    simple wrong guess: the code expired (EMAIL_OTP_EXPIRE_MINUTES),
    it was already used once before, or the account has racked up too
    many wrong attempts already (EMAIL_OTP_MAX_ATTEMPTS -- a 429, not a
    400, so the frontend can tell "wrong code" apart from "locked out,
    request a new one instead").
    """
    invalid = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code")

    token = await db.scalar(
        select(EmailVerificationToken)
        .where(EmailVerificationToken.user_id == current_user.id, EmailVerificationToken.used_at.is_(None))
        .order_by(EmailVerificationToken.created_at.desc())
    )
    now = dt.datetime.now(dt.timezone.utc)
    if token is None or as_aware_utc(token.expires_at) < now:
        raise invalid
    if token.attempts >= settings.EMAIL_OTP_MAX_ATTEMPTS:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts, request a new code")

    if hash_token(payload.code) != token.code_hash:
        token.attempts += 1
        await db.commit()
        raise invalid

    token.used_at = now
    current_user.is_email_verified = True
    await db.commit()
    return MessageResponse(message="Email verified")

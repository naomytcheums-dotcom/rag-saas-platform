"""1.1.3 -- forgot/reset password. /forgot always answers the same generic
message whether or not the email exists, so it can't be used to enumerate
registered accounts."""

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from api.models.session import Session
from api.models.token import PasswordResetToken
from api.models.user import User
from api.schemas.auth import MessageResponse, PasswordForgotRequest, PasswordResetRequest
from api.security.hashing import hash_password, hash_token
from api.services.password_reset import create_and_send_password_reset
from api.utils import as_aware_utc

router = APIRouter(prefix="/auth/password", tags=["auth"])

_GENERIC_FORGOT_MESSAGE = "If an account exists for that email, a reset link has been sent."


@router.post("/forgot", response_model=MessageResponse)
async def forgot_password(payload: PasswordForgotRequest, db: AsyncSession = Depends(get_db)):
    """
    Step 1 of the "forgot my password" flow: emails a one-time reset link
    if the address belongs to a real, active account. Always returns the
    exact same success message either way (see _GENERIC_FORGOT_MESSAGE
    above) -- an attacker probing random emails can't tell which ones are
    registered from this endpoint's response alone.
    """
    user = await db.scalar(select(User).where(User.email == payload.email))
    if user is not None and user.is_active and not user.is_deleted:
        await create_and_send_password_reset(db, user)
        await db.commit()
    return MessageResponse(message=_GENERIC_FORGOT_MESSAGE)


@router.post("/reset", response_model=MessageResponse)
async def reset_password(payload: PasswordResetRequest, db: AsyncSession = Depends(get_db)):
    """
    Step 2: the user clicked the link from their email (containing the
    raw token) and submits a new password here. The token is checked
    against its stored hash, must not be expired, and must not have been
    used already (used_at gets set below, so a second attempt with the
    same link fails cleanly instead of silently resetting the password
    again for whoever has the link).
    """
    invalid = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    reset_row = await db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(payload.token)))
    now = dt.datetime.now(dt.timezone.utc)
    if reset_row is None or reset_row.used_at is not None or as_aware_utc(reset_row.expires_at) < now:
        raise invalid

    user = await db.get(User, reset_row.user_id)
    if user is None:
        raise invalid

    user.hashed_password = hash_password(payload.new_password)
    reset_row.used_at = now

    # A password reset is a strong signal of possible compromise -- log
    # every device out, don't just change the password under them.
    await db.execute(delete(Session).where(Session.user_id == user.id))

    await db.commit()
    return MessageResponse(message="Password has been reset. Please log in again.")

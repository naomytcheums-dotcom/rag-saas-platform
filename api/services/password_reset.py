"""1.1.3 -- mirrors verification.py's shape for the password-reset token."""

import datetime as dt
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.token import PasswordResetToken
from api.models.user import User
from api.security.hashing import generate_raw_token, hash_token
from api.services.email import send_password_reset_email

logger = logging.getLogger(__name__)


async def create_and_send_password_reset(db: AsyncSession, user: User) -> None:
    """Generates a fresh high-entropy reset token, stores only its hash
    (with an expiry), and emails a link containing the raw token. Same
    "caller commits" contract as create_and_send_email_otp above."""
    raw_token = generate_raw_token()
    reset_row = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
    )
    db.add(reset_row)
    await db.flush()

    reset_link = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?token={raw_token}"
    try:
        send_password_reset_email(user.email, reset_link)
    except (EnvironmentError, RuntimeError) as exc:
        logger.warning("failed to send password reset email to %s: %s", user.email, exc)

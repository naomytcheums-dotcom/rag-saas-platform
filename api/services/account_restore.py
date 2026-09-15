"""1.1.10 -- mirrors password_reset.py's shape for the account-restore token."""

import asyncio
import datetime as dt
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.restore_token import AccountRestoreToken
from api.models.user import User
from api.security.hashing import generate_raw_token, hash_token
from api.services.email import send_account_restore_email

logger = logging.getLogger(__name__)


async def create_and_send_account_restore(db: AsyncSession, user: User) -> None:
    """Generates a fresh high-entropy restore token, stores only its hash
    (with an expiry), and emails a link containing the raw token. Same
    "caller commits" contract as password_reset.py's
    create_and_send_password_reset -- this only stages the INSERT and
    flushes it, the caller's own db.commit() is what makes it durable."""
    raw_token = generate_raw_token()
    restore_row = AccountRestoreToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=settings.ACCOUNT_RESTORE_TOKEN_EXPIRE_MINUTES),
    )
    db.add(restore_row)
    await db.flush()

    restore_link = f"{settings.FRONTEND_URL.rstrip('/')}/restore-account?token={raw_token}"
    try:
        await asyncio.to_thread(send_account_restore_email, user.email, restore_link)
    except (EnvironmentError, RuntimeError) as exc:
        logger.warning("failed to send account restore email to %s: %s", user.email, exc)

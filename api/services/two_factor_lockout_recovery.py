"""1.1.7 -- mirrors password_reset.py's shape for the 2FA lockout-recovery token."""

import datetime as dt
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.lockout_recovery_token import TwoFactorLockoutRecoveryToken
from api.models.user import User
from api.security.hashing import generate_raw_token, hash_token
from api.services.email import send_two_factor_lockout_recovery_requested_email

logger = logging.getLogger(__name__)


async def create_and_send_two_factor_lockout_recovery(db: AsyncSession, user: User) -> None:
    """Generates a fresh high-entropy token, stores only its hash (with
    an expiry measured from now), and emails a link that won't actually
    work until TWO_FA_LOCKOUT_RECOVERY_DELAY_HOURS have passed -- see
    api/routers/two_factor.py's confirm_two_factor_lockout_recovery for
    where that delay is enforced. Same "caller commits" contract as
    password_reset.py's create_and_send_password_reset."""
    raw_token = generate_raw_token()
    row = TwoFactorLockoutRecoveryToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=settings.TWO_FA_LOCKOUT_RECOVERY_TOKEN_EXPIRE_HOURS),
    )
    db.add(row)
    await db.flush()

    confirm_link = f"{settings.FRONTEND_URL.rstrip('/')}/2fa-lockout-recovery?token={raw_token}"
    try:
        send_two_factor_lockout_recovery_requested_email(user.email, confirm_link, settings.TWO_FA_LOCKOUT_RECOVERY_DELAY_HOURS)
    except (EnvironmentError, RuntimeError) as exc:
        logger.warning("failed to send 2FA lockout recovery email to %s: %s", user.email, exc)

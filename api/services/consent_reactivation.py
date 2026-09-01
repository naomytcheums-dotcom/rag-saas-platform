"""1.1.12 -- mirrors account_restore.py's shape for the consent-reactivation token."""

import datetime as dt
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.consent_reactivation_token import ConsentReactivationToken
from api.models.user import User
from api.security.hashing import generate_raw_token, hash_token
from api.services.email import send_consent_reactivation_email

logger = logging.getLogger(__name__)


async def create_and_send_consent_reactivation(db: AsyncSession, user: User) -> None:
    """Generates a fresh high-entropy token, stores only its hash (with
    an expiry), and emails a link containing the raw token. Reuses
    ACCOUNT_RESTORE_TOKEN_EXPIRE_MINUTES rather than a dedicated setting
    -- "come back to an account you stepped away from" is the same
    urgency profile whether the account was deleted or deactivated, no
    need for a second knob that would always be set to the same value.
    Same "caller commits" contract as account_restore.py's
    create_and_send_account_restore."""
    raw_token = generate_raw_token()
    row = ConsentReactivationToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=settings.ACCOUNT_RESTORE_TOKEN_EXPIRE_MINUTES),
    )
    db.add(row)
    await db.flush()

    reactivation_link = f"{settings.FRONTEND_URL.rstrip('/')}/reactivate-consent?token={raw_token}"
    try:
        send_consent_reactivation_email(user.email, reactivation_link)
    except (EnvironmentError, RuntimeError) as exc:
        logger.warning("failed to send consent reactivation email to %s: %s", user.email, exc)

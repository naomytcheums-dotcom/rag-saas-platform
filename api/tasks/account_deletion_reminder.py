"""
4.6 -- the second of two deletion warnings. DELETE /account/me
(api/routers/account.py) already emails an immediate confirmation the
moment deletion is requested; this is a closer-to-the-deadline "last
chance" reminder, run daily by Celery beat, same pattern as
account_purge.py and token_blacklist_cleanup.py.

A single email 30 days before the purge is easy to forget by the time it
actually matters -- this is what real products (GitHub, Google) do for
the same scenario: warn again as the deadline actually approaches.
"""

import datetime as dt
import logging

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session as SyncSession

from api.config import settings
from api.models.user import User
from api.services.email import send_account_deletion_reminder_email
from api.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_sync_engine = create_engine(settings.DATABASE_URL.replace("+asyncpg", ""), pool_pre_ping=True)


@celery_app.task(name="api.tasks.account_deletion_reminder.send_pending_deletion_reminders")
def send_pending_deletion_reminders() -> int:
    """
    Finds every account whose deletion_scheduled_at falls within
    ACCOUNT_DELETION_REMINDER_DAYS_BEFORE of now, that hasn't already
    gotten this reminder this deletion cycle (deletion_reminder_sent_at
    IS NULL -- cleared on restore, see api/routers/account.py's
    confirm_account_restore, so a later deletion cycle is eligible
    again). Safe to run repeatedly: a user who already got the reminder
    is excluded on the next run, so re-running (or running more often
    than daily) doesn't spam them.

    deletion_reminder_sent_at is only set on a SUCCESSFUL send -- a
    transient Resend outage leaves it eligible to retry on the next run,
    rather than silently skipping the one warning that actually matters,
    for good.
    """
    now = dt.datetime.now(dt.timezone.utc)
    threshold = now + dt.timedelta(days=settings.ACCOUNT_DELETION_REMINDER_DAYS_BEFORE)
    sent = 0

    with SyncSession(_sync_engine) as db:
        due = db.scalars(
            select(User).where(
                User.deletion_scheduled_at.is_not(None),
                User.deletion_scheduled_at <= threshold,
                User.deletion_scheduled_at > now,
                User.deletion_reminder_sent_at.is_(None),
            )
        ).all()
        for user in due:
            days_remaining = max((user.deletion_scheduled_at - now).days, 0)
            try:
                send_account_deletion_reminder_email(user.email, days_remaining)
            except (EnvironmentError, RuntimeError) as exc:
                logger.warning("failed to send deletion reminder to %s: %s", user.email, exc)
                continue
            user.deletion_reminder_sent_at = now
            sent += 1
        db.commit()

    logger.info("send_pending_deletion_reminders: sent %d reminder(s)", sent)
    return sent

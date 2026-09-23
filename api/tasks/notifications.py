"""Phase 5, Étape 4 -- notification email delivery + cleanup, same
asyncio.run() bridge as every other real Celery task in this codebase
(api/tasks/document_processing.py, api/tasks/workflows.py) and for the
identical reason: the real work stays async for the routes/tests that
also call it directly."""

import asyncio
import datetime as dt
import logging
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.models.notification import Notification
from api.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _session_factory():
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    return engine, async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


async def _send_notification_email_async(notification_id: str) -> str:
    from api.services.notifications import send_notification_email

    engine, session_factory = _session_factory()
    try:
        async with session_factory() as db:
            await send_notification_email(db, uuid.UUID(notification_id))
            await db.commit()
            notification = await db.get(Notification, uuid.UUID(notification_id))
            return notification.email_status if notification else "not_found"
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.notifications.send_notification_email_task")
def send_notification_email_task(notification_id: str) -> str:
    """Dispatched by api/services/notifications.create_notification
    right after a notification with email_enabled is persisted."""
    return asyncio.run(_send_notification_email_async(notification_id))


async def _retry_failed_notifications_async(max_retries: int = 3) -> int:
    engine, session_factory = _session_factory()
    try:
        async with session_factory() as db:
            stmt = select(Notification.id).where(Notification.email_status == "failed", Notification.email_retry_count < max_retries)
            ids = list((await db.scalars(stmt)).all())
    finally:
        await engine.dispose()

    for notification_id in ids:
        # Reset to "pending" so send_notification_email's own
        # idempotency check (email_status != "pending" -> no-op) lets
        # this retry actually go through -- a real, separate DB
        # round-trip per retry, not a bulk update, since each send is
        # itself a real, isolated network call that can fail
        # independently.
        engine2, session_factory2 = _session_factory()
        try:
            async with session_factory2() as db:
                notification = await db.get(Notification, notification_id)
                if notification is not None:
                    notification.email_status = "pending"
                    await db.commit()
        finally:
            await engine2.dispose()
        send_notification_email_task.delay(str(notification_id))
    return len(ids)


@celery_app.task(name="api.tasks.notifications.retry_failed_notifications_task")
def retry_failed_notifications_task() -> int:
    """Real Celery Beat job -- re-queues every notification whose email
    failed and hasn't yet exhausted its retry budget (3 attempts)."""
    return asyncio.run(_retry_failed_notifications_async())


async def _purge_old_notifications_async(read_retention_days: int = 90, expired_grace_days: int = 0) -> int:
    now = dt.datetime.now(dt.timezone.utc)
    engine, session_factory = _session_factory()
    try:
        async with session_factory() as db:
            cutoff = now - dt.timedelta(days=read_retention_days)
            result = await db.execute(
                delete(Notification).where(
                    (Notification.read_at.is_not(None)) & (Notification.read_at < cutoff)
                    | (Notification.expires_at.is_not(None)) & (Notification.expires_at < now - dt.timedelta(days=expired_grace_days))
                )
            )
            await db.commit()
            return result.rowcount or 0
    finally:
        await engine.dispose()


@celery_app.task(name="api.tasks.notifications.purge_old_notifications_task")
def purge_old_notifications_task(read_retention_days: int = 90) -> int:
    """Real Celery Beat job -- deletes notifications read more than
    `read_retention_days` ago, and any notification past its own real
    `expires_at`. Never deletes an unread, non-expired notification,
    regardless of age -- age alone is never a reason to hide something
    a user hasn't seen yet."""
    return asyncio.run(_purge_old_notifications_async(read_retention_days))

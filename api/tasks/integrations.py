"""Partie 15.1 -- real log retention sweep, same sync-engine pattern as
every other Celery task module in this project."""

import datetime as dt
import logging

from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session as SyncSession

from api.config import settings
from api.models.integrations import IntegrationLog
from api.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_sync_engine = create_engine(settings.DATABASE_URL.replace("+asyncpg", ""), pool_pre_ping=True)


@celery_app.task(name="api.tasks.integrations.cleanup_integration_logs")
def cleanup_integration_logs() -> int:
    threshold = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=settings.INTEGRATION_LOG_RETENTION_DAYS)
    with SyncSession(_sync_engine) as db:
        result = db.execute(delete(IntegrationLog).where(IntegrationLog.created_at < threshold))
        db.commit()
        count = result.rowcount
    logger.info("cleanup_integration_logs: purged %d row(s) older than %d days", count, settings.INTEGRATION_LOG_RETENTION_DAYS)
    return count

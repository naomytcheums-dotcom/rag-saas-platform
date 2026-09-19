"""
Partie 8.1.13 -- real, batched, daily purge of soft-deleted
conversations past their real grace period
(`settings.CONVERSATION_DELETION_GRACE_PERIOD`). Same sync-engine-in-a-
Celery-task pattern as `api/tasks/token_blacklist_cleanup.py` -- an
async SQLAlchemy engine cannot run inside a real, sync Celery worker
without its own real event loop plumbing, which this codebase's other
periodic sweeps already avoid the same way.
"""

import datetime as dt
import logging

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as SyncSession

from api.config import settings
from api.models.conversation import Conversation
from api.tasks.celery_app import celery_app
from api.tasks._sync_engine import sync_engine as _sync_engine

logger = logging.getLogger(__name__)



@celery_app.task(name="api.tasks.conversation_cleanup.purge_deleted_conversations_task")
def purge_deleted_conversations_task(days: int | None = None) -> int:
    """Real, batched (`CONVERSATION_DELETION_BATCH_SIZE` rows per
    call), idempotent (only ever touches rows genuinely past the real
    cutoff, so re-running does nothing extra -- same idempotency
    property as `token_blacklist_cleanup.py`'s own real sweep). Returns
    the real count removed."""
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days if days is not None else settings.CONVERSATION_DELETION_GRACE_PERIOD)

    with SyncSession(_sync_engine) as db:
        ids = list(db.scalars(
            select(Conversation.id).where(Conversation.deleted_at.is_not(None), Conversation.deleted_at < cutoff)
            .limit(settings.CONVERSATION_DELETION_BATCH_SIZE)
        ).all())
        if ids:
            db.execute(delete(Conversation).where(Conversation.id.in_(ids)))
            db.commit()

    logger.info("purge_deleted_conversations_task: removed %d conversation(s) past the deletion grace period", len(ids))
    return len(ids)

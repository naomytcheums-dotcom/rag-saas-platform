"""Spec 10.4.5 / 10.4.6 -- per-organization data retention.

An organization can set `conversation_retention_days` in its settings (PATCH /organizations/{id}/settings). Once a day this task permanently
deletes that organization's conversations (their messages, feedback and shares cascade) whose last activity is older than that many days.
An organization without the setting keeps everything. Only conversations of the organization that set the policy are ever touched, in batches.
"""

import datetime as dt
import logging

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as SyncSession

from api.models.conversation import Conversation
from api.models.organization_settings import OrganizationSettings
from api.tasks._sync_engine import sync_engine as _sync_engine
from api.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

BATCH_SIZE = 500


def purge_expired_conversations(db: SyncSession, now: dt.datetime | None = None, batch_size: int = BATCH_SIZE) -> dict[str, int]:
    """Apply every organization's retention policy once. Returns `{organization_id: deleted_count}` for the organizations that lost conversations."""
    now = now or dt.datetime.now(dt.timezone.utc)
    removed: dict[str, int] = {}
    for row in db.execute(select(OrganizationSettings.organization_id, OrganizationSettings.settings)).all():
        days = (row.settings or {}).get("conversation_retention_days")
        if not isinstance(days, int) or isinstance(days, bool) or days < 1:
            continue
        cutoff = now - dt.timedelta(days=days)
        ids = list(db.scalars(
            select(Conversation.id).where(Conversation.organization_id == row.organization_id, Conversation.updated_at < cutoff).limit(batch_size)
        ).all())
        if ids:
            db.execute(delete(Conversation).where(Conversation.id.in_(ids), Conversation.organization_id == row.organization_id))
            removed[str(row.organization_id)] = len(ids)
    db.commit()
    return removed


@celery_app.task(name="api.tasks.retention.purge_expired_conversations_task")
def purge_expired_conversations_task() -> int:
    with SyncSession(_sync_engine) as db:
        removed = purge_expired_conversations(db)
    total = sum(removed.values())
    logger.info("purge_expired_conversations_task: removed %d conversation(s) across %d organization(s)", total, len(removed))
    return total

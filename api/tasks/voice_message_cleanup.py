"""Partie 8.2.7 -- real, daily purge of voice messages past their real
retention window (`settings.AUDIO_HISTORY_RETENTION_DAYS`). Same
sync-engine-in-a-Celery-task pattern as
`api/tasks/conversation_cleanup.py`."""

import datetime as dt
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session as SyncSession

from api.config import settings
from api.models.voice import VoiceMessage
from api.tasks.celery_app import celery_app
from api.tasks._sync_engine import sync_engine as _sync_engine

logger = logging.getLogger(__name__)



@celery_app.task(name="api.tasks.voice_message_cleanup.purge_expired_voice_messages_task")
def purge_expired_voice_messages_task(days: int | None = None) -> int:
    """Real, idempotent (only ever touches rows genuinely past the
    real cutoff). Also deletes each real row's own real S3 object, so
    expired audio never lingers in storage after its own database row
    is gone."""
    from api.services.voice_storage import delete_voice_recording

    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days if days is not None else settings.AUDIO_HISTORY_RETENTION_DAYS)

    with SyncSession(_sync_engine) as db:
        expired = list(db.scalars(select(VoiceMessage).where(VoiceMessage.created_at < cutoff)).all())
        for message in expired:
            if message.audio_key:
                try:
                    delete_voice_recording(message.audio_key)
                except RuntimeError:
                    logger.warning("purge_expired_voice_messages_task: failed to delete S3 object for message %s", message.id)
            db.delete(message)
        db.commit()

    logger.info("purge_expired_voice_messages_task: removed %d voice message(s) past the retention window", len(expired))
    return len(expired)

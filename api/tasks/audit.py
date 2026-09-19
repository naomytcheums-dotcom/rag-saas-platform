"""Partie 10.2 -- scheduled audit-log retention/archival, run by Celery
Beat. Real, config-driven (AUDIT_RETENTION_DAYS, AUDIT_ARCHIVE_MONTHS) --
distinct from DELETE /audit/logs/purge (api/routers/audit.py), which is
a manual, on-demand Owner-triggered operation."""

import datetime as dt
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session as SyncSession

from api.config import settings
from api.models.audit_log import AuditLog, AuditLogArchive
from api.tasks.celery_app import celery_app
from api.tasks._sync_engine import sync_engine as _sync_engine

logger = logging.getLogger(__name__)



@celery_app.task(name="api.tasks.audit.archive_logs")
def archive_logs(months: int | None = None) -> int:
    """Copies every row older than `months` (default: AUDIT_ARCHIVE_MONTHS)
    into audit_logs_archive, then deletes it from the live table -- a
    real move, not a delete-only purge (see DELETE /audit/logs/purge's
    own docstring for why that one IS delete-only and deliberately so)."""
    import uuid

    months = months if months is not None else settings.AUDIT_ARCHIVE_MONTHS
    threshold = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=months * 30)
    archived = 0
    with SyncSession(_sync_engine) as db:
        rows = db.execute(select(AuditLog).where(AuditLog.timestamp < threshold)).scalars().all()
        for row in rows:
            db.add(AuditLogArchive(
                id=uuid.uuid4(), original_id=row.id, user_id=row.user_id, organization_id=row.organization_id,
                resource_type=row.resource_type, resource_id=row.resource_id, action=row.action, ip=row.ip,
                user_agent=row.user_agent, timestamp=row.timestamp, metadata_json=row.metadata_json,
                success=row.success, failure_reason=row.failure_reason, checksum=row.checksum,
            ))
            db.delete(row)
            archived += 1
        db.commit()
    return archived


@celery_app.task(name="api.tasks.audit.purge_old_logs")
def purge_old_logs(days: int | None = None) -> int:
    """The scheduled counterpart to the manual DELETE /audit/logs/purge
    endpoint -- same real semantics (see that endpoint's own docstring
    on the hash chain implication), config-driven via AUDIT_RETENTION_DAYS."""
    days = days if days is not None else settings.AUDIT_RETENTION_DAYS
    threshold = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    with SyncSession(_sync_engine) as db:
        rows = db.execute(select(AuditLog).where(AuditLog.timestamp < threshold)).scalars().all()
        count = len(rows)
        for row in rows:
            db.delete(row)
        db.commit()
    return count

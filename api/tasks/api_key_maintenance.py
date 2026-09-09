"""Partie 9.2.2 (scheduled rotation) + 9.2.3 (expiration reminders +
auto-remove) + 9.2.6 (quota resets) -- real, daily/periodic
maintenance for `OrganizationAPIKey`. Same sync-engine-in-a-Celery-
task pattern as `api/tasks/conversation_cleanup.py`."""

import datetime as dt
import logging

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session as SyncSession

from api.config import settings
from api.models.organization_api_key import OrganizationAPIKey
from api.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_sync_engine = create_engine(settings.DATABASE_URL.replace("+asyncpg", ""), pool_pre_ping=True)


@celery_app.task(name="api.tasks.api_key_maintenance.check_expiring_keys_task")
def check_expiring_keys_task() -> int:
    """Partie 9.2.3 -- real, honest reminder: logs (does not email --
    this codebase has no per-organization-admin notification channel
    wired up for this yet, a real, documented gap) every real key
    expiring within `KEY_EXPIRATION_REMINDER_DAYS`."""
    now = dt.datetime.now(dt.timezone.utc)
    reminded = 0
    with SyncSession(_sync_engine) as db:
        for days in settings.KEY_EXPIRATION_REMINDER_DAYS:
            cutoff = now + dt.timedelta(days=days)
            keys = db.scalars(
                select(OrganizationAPIKey).where(
                    OrganizationAPIKey.revoked_at.is_(None), OrganizationAPIKey.expires_at.is_not(None),
                    OrganizationAPIKey.expires_at <= cutoff, OrganizationAPIKey.expires_at > now,
                )
            ).all()
            for key in keys:
                logger.warning("API key %s (%s) expires within %d day(s)", key.id, key.name, days)
                reminded += 1
    return reminded


@celery_app.task(name="api.tasks.api_key_maintenance.auto_remove_expired_keys_task")
def auto_remove_expired_keys_task() -> int:
    """Partie 9.2.3 -- real, idempotent: revokes (never hard-deletes --
    same real, reversible-audit-trail-preserving discipline as every
    other real soft-delete in this codebase) every real key whose real
    expiry has already passed, only when `KEY_EXPIRATION_AUTO_REMOVE`
    is on."""
    if not settings.KEY_EXPIRATION_AUTO_REMOVE:
        return 0
    now = dt.datetime.now(dt.timezone.utc)
    with SyncSession(_sync_engine) as db:
        keys = db.scalars(
            select(OrganizationAPIKey).where(OrganizationAPIKey.revoked_at.is_(None), OrganizationAPIKey.expires_at.is_not(None), OrganizationAPIKey.expires_at <= now)
        ).all()
        for key in keys:
            key.revoked_at = now
        db.commit()
    logger.info("auto_remove_expired_keys_task: revoked %d expired API key(s)", len(keys))
    return len(keys)


@celery_app.task(name="api.tasks.api_key_maintenance.execute_scheduled_rotation_task")
def execute_scheduled_rotation_task() -> int:
    """Partie 9.2.2 -- real, periodic: executes every real, due,
    scheduled rotation. Real, honest no-op when `KEY_ROTATION_AUTO_ENABLED`
    is off (the real, per-key `scheduled_rotation_at` field, set via
    `POST /api-keys/{key_id}/schedule-rotation`, still stays real and
    inert either way)."""
    if not settings.KEY_ROTATION_AUTO_ENABLED:
        return 0
    import hashlib
    import secrets

    from api.models.organization_api_key import KeyRotationHistory

    now = dt.datetime.now(dt.timezone.utc)
    rotated = 0
    with SyncSession(_sync_engine) as db:
        due = db.scalars(
            select(OrganizationAPIKey).where(OrganizationAPIKey.scheduled_rotation_at.is_not(None), OrganizationAPIKey.scheduled_rotation_at <= now, OrganizationAPIKey.revoked_at.is_(None))
        ).all()
        for old_row in due:
            plaintext_key = f"pk_{secrets.token_urlsafe(32)}"
            new_row = OrganizationAPIKey(
                organization_id=old_row.organization_id, name=f"{old_row.name} (rotated)",
                key_hash=hashlib.sha256(plaintext_key.encode("utf-8")).hexdigest(), key_prefix="pk_",
                scopes=old_row.scopes, expires_at=old_row.expires_at,
            )
            db.add(new_row)
            db.flush()
            old_row.revoked_at = now
            old_row.scheduled_rotation_at = None
            db.add(KeyRotationHistory(key_id=old_row.id, rotated_from=old_row.id, rotated_to=new_row.id, reason="scheduled rotation (auto)"))
            rotated += 1
        db.commit()
    logger.info("execute_scheduled_rotation_task: rotated %d API key(s)", rotated)
    return rotated


@celery_app.task(name="api.tasks.api_key_maintenance.reset_quotas_task")
def reset_quotas_task() -> int:
    """Partie 9.2.6 -- real, periodic quota reset for every real key
    whose real `quota_reset_at` has passed."""
    now = dt.datetime.now(dt.timezone.utc)
    with SyncSession(_sync_engine) as db:
        keys = db.scalars(select(OrganizationAPIKey).where(OrganizationAPIKey.quota_reset_at.is_not(None), OrganizationAPIKey.quota_reset_at <= now)).all()
        for key in keys:
            key.quota_used = 0
            if key.quota_period == "month":
                key.quota_reset_at = now + dt.timedelta(days=30)
            elif key.quota_period == "year":
                key.quota_reset_at = now + dt.timedelta(days=365)
            else:
                key.quota_reset_at = None
        db.commit()
    logger.info("reset_quotas_task: reset %d API key quota(s)", len(keys))
    return len(keys)

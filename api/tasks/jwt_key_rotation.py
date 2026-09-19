"""
Audit finding 28 -- automatic JWT signing-key rotation, run by Celery
Beat on the schedule in api/tasks/celery_app.py's beat_schedule (only
registered if JWT_AUTO_ROTATION_INTERVAL_DAYS > 0 -- see that module).
A plain sync SQLAlchemy engine, same reasoning as
api/tasks/account_purge.py's own module docstring (Celery's worker model
is sync-by-default; a once-a-rotation-interval job has no need for the
app's async engine).

"Automatic" here means: this task is the ONLY thing that ever writes a
new active key or retires the old one -- no admin action, no redeploy.
A running API process picks up the change on its own
JWT_KEY_CACHE_REFRESH_SECONDS timer (api/security/jwt.py's
refresh_jwt_key_cache, called from api/main.py's lifespan) -- this task
and that timer together are what make rotation actually automatic across
every worker process, not just this task alone.
"""

import datetime as dt
import logging
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session as SyncSession

from api.config import settings
from api.models.jwt_signing_key import JWTSigningKey
from api.security.secret_encryption import encrypt_secret
from api.services.email import send_jwt_key_rotated_email
from api.tasks.celery_app import celery_app
from api.tasks._sync_engine import sync_engine as _sync_engine

logger = logging.getLogger(__name__)


# Same generation approach .env.example already recommends for
# JWT_SECRET_KEY itself (secrets.token_urlsafe) -- a fresh, independent
# random value each rotation, never derived from the previous key.
_NEW_KEY_BYTES = 48


@celery_app.task(name="api.tasks.jwt_key_rotation.rotate_jwt_signing_key")
def rotate_jwt_signing_key() -> bool:
    """
    Idempotent and safe to run on any schedule, same property
    account_purge.py's task documents for itself: does nothing (returns
    False) unless the current active key is genuinely due --
    JWT_AUTO_ROTATION_INTERVAL_DAYS have passed since it was created, OR
    no active key exists yet at all (first-ever run, bootstrapping the
    table from nothing).

    A rotation is two writes in one transaction: the old active key gets
    retired_at=now (still valid for VERIFYING existing tokens until
    JWT_KEY_RETENTION_DAYS later -- see api/security/jwt.py), and a
    brand-new key is inserted active. Returns True iff a rotation
    actually happened, mainly so a manual invocation or a test can assert
    on it.
    """
    if settings.JWT_AUTO_ROTATION_INTERVAL_DAYS <= 0:
        logger.info("rotate_jwt_signing_key: JWT_AUTO_ROTATION_INTERVAL_DAYS is 0 -- automatic rotation is disabled, skipping")
        return False

    now = dt.datetime.now(dt.timezone.utc)

    with SyncSession(_sync_engine) as db:
        active_key = db.scalar(select(JWTSigningKey).where(JWTSigningKey.is_active.is_(True)))

        if active_key is not None:
            due_at = active_key.created_at
            if due_at.tzinfo is None:
                due_at = due_at.replace(tzinfo=dt.timezone.utc)
            if now < due_at + dt.timedelta(days=settings.JWT_AUTO_ROTATION_INTERVAL_DAYS):
                logger.info("rotate_jwt_signing_key: current key is not due for rotation yet, skipping")
                return False
            active_key.is_active = False
            active_key.retired_at = now

        new_secret = secrets.token_urlsafe(_NEW_KEY_BYTES)
        db.add(JWTSigningKey(secret=encrypt_secret(new_secret), is_active=True))
        db.commit()

    logger.info("rotate_jwt_signing_key: rotated the active JWT signing key")
    if settings.JWT_KEY_ROTATION_ADMIN_EMAIL:
        try:
            send_jwt_key_rotated_email(
                settings.JWT_KEY_ROTATION_ADMIN_EMAIL, rotated_at_iso=now.isoformat(), retention_days=settings.JWT_KEY_RETENTION_DAYS,
            )
        except (EnvironmentError, RuntimeError) as exc:
            logger.warning("failed to send JWT-key-rotation admin notification: %s", exc)
    return True

"""
1.1.15 -- housekeeping for the access-token blacklist (api/models/revoked_token.py).
Every row there is only ever meaningful until the access token it names
would have expired naturally anyway (api/dependencies.py's get_current_user
rejects an expired token on signature/claims grounds regardless of whether
it's also blacklisted) -- past that point the row is dead weight. Run
daily by Celery beat, same pattern as account_purge.py, so this table
doesn't grow forever on an app with any real amount of login/logout
traffic.

Same sync-engine-in-a-Celery-task reasoning as account_purge.py.
"""

import datetime as dt
import logging

from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session as SyncSession

from api.config import settings
from api.models.revoked_token import RevokedAccessToken
from api.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_sync_engine = create_engine(settings.DATABASE_URL.replace("+asyncpg", ""), pool_pre_ping=True)


@celery_app.task(name="api.tasks.token_blacklist_cleanup.purge_expired_blacklist_entries")
def purge_expired_blacklist_entries() -> int:
    """
    Deletes every blacklist row whose underlying access token has already
    expired on its own terms. Safe to run on any schedule, any number of
    times: it only ever touches rows that are genuinely past their
    expires_at, so re-running does nothing extra -- same idempotency
    property as account_purge.py's purge_deleted_accounts. Returns the
    count removed, for manual invocation / tests to assert on.
    """
    now = dt.datetime.now(dt.timezone.utc)

    with SyncSession(_sync_engine) as db:
        result = db.execute(delete(RevokedAccessToken).where(RevokedAccessToken.expires_at <= now))
        removed = result.rowcount
        db.commit()

    logger.info("purge_expired_blacklist_entries: removed %d blacklist row(s) for already-expired access tokens", removed)
    return removed

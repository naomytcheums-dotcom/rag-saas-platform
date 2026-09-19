"""
1.1.10 -- the actual hard-delete, run daily by celery beat (see
celery_app.py's beat_schedule), never inline in the DELETE /account
request itself: the user gets an immediate, fast response, and the
30-day grace window (settings.ACCOUNT_PURGE_DELAY_DAYS) is enforced here
by simply not selecting rows whose window hasn't elapsed yet.

A plain synchronous SQLAlchemy engine is used in this module rather than
the app's async one -- Celery's worker model is sync-by-default, and
pulling the async engine into a sync task would need its own event loop
plumbing for no real benefit at this scale (a once-a-day batch job).
"""

import datetime as dt
import logging

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as SyncSession

from api.config import settings
from api.models.organization import Organization, OrganizationMember
from api.models.user import User
from api.services.storage import delete_avatar
from api.tasks.celery_app import celery_app
from api.tasks._sync_engine import sync_engine as _sync_engine

logger = logging.getLogger(__name__)



@celery_app.task(name="api.tasks.account_purge.purge_deleted_accounts")
def purge_deleted_accounts() -> int:
    """
    Finds every account whose grace period has elapsed
    (deletion_scheduled_at <= now) and permanently deletes it. Safe to
    run repeatedly / on any schedule: it only ever touches rows that
    are actually due, so running it twice in a row (or by accident
    outside of Celery Beat's own schedule) just does nothing on the
    second run instead of double-deleting or erroring -- see
    tests/test_celery_integration.py's idempotency test. Returns the
    count of accounts actually purged, mainly so a manual invocation or
    a test can assert on it.
    """
    now = dt.datetime.now(dt.timezone.utc)
    purged = 0

    with SyncSession(_sync_engine) as db:
        due = db.scalars(
            select(User).where(User.deletion_scheduled_at.is_not(None), User.deletion_scheduled_at <= now)
        ).all()
        for user in due:
            # The avatar object lives in S3/R2/Supabase Storage, outside
            # this database entirely -- ON DELETE CASCADE below only
            # reaches FK-linked *tables* (oauth_accounts, sessions,
            # tokens), never external storage, so it has to be cleaned up
            # explicitly here or it's orphaned forever.
            if user.avatar_url:
                delete_avatar(user.avatar_url)

            # organizations.id has no owner FK, so ON DELETE CASCADE never
            # reaches it -- an org whose only member was this user would
            # otherwise survive forever with zero members and no possible
            # owner. Delete it now, before the membership row itself is
            # cascaded away by the user delete below.
            member_org_ids = db.scalars(
                select(OrganizationMember.organization_id).where(OrganizationMember.user_id == user.id)
            ).all()
            for org_id in member_org_ids:
                other_members = db.scalar(
                    select(OrganizationMember.id)
                    .where(OrganizationMember.organization_id == org_id, OrganizationMember.user_id != user.id)
                    .limit(1)
                )
                if other_members is None:
                    db.execute(delete(Organization).where(Organization.id == org_id))

            db.execute(delete(User).where(User.id == user.id))
            purged += 1
        db.commit()

    logger.info("purge_deleted_accounts: hard-deleted %d account(s) past their %d-day grace window", purged, settings.ACCOUNT_PURGE_DELAY_DAYS)
    return purged

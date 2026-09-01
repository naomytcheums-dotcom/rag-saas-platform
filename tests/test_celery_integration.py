"""
1.1.10's purge task, tested two ways for two different things:

1. Here (automated, runs every `pytest`): the task's own logic --
   filtering, safety (an active/not-yet-due account is never touched),
   idempotency -- executed via Celery's `.apply()` against the real
   Postgres dev database. `.apply()` runs the task body synchronously in
   this process, no broker/worker needed, so this always runs in CI.

2. Manually (documented in README.md's "Running the full Celery chain"
   section, not automated here): the actual declencheur -> Redis -> worker
   -> task -> Postgres chain, with a real `celery worker` process
   consuming from a real Redis broker. That's an infra/process lifecycle
   concern, not unit-test-shaped -- bundling a worker subprocess into a
   pytest fixture would trade a small amount of coverage for a lot of
   flakiness. It was run and verified manually while building this task;
   the runbook lets anyone repeat that verification on demand.
"""

import datetime as dt
import uuid

import boto3
import pytest
from botocore.exceptions import ClientError
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import create_async_engine

from api.config import settings
from api.models.user import User
from api.services.storage import upload_avatar
from api.tasks.account_purge import purge_deleted_accounts

# Loop scope is set globally to "session" in pyproject.toml, not pinned
# per-file here -- see that file's comment for why.


@pytest.fixture(scope="module")
async def pg_engine():
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"DATABASE_URL is not reachable -- skipping Celery/purge integration tests ({exc})")
    yield engine
    await engine.dispose()


async def _create_user(pg_engine, **overrides):
    email = f"celery-purge-{uuid.uuid4().hex[:10]}@example.com"
    defaults = {"email": email, "hashed_password": "irrelevant", "is_active": True}
    defaults.update(overrides)
    async with pg_engine.begin() as conn:
        await conn.execute(User.__table__.insert().values(**defaults))
    return email


async def _exists(pg_engine, email) -> bool:
    async with pg_engine.connect() as conn:
        result = await conn.execute(select(User.id).where(User.email == email))
        return result.first() is not None


async def test_purge_task_deletes_only_accounts_past_their_grace_window(pg_engine):
    now = dt.datetime.now(dt.timezone.utc)

    overdue_email = await _create_user(
        pg_engine, is_active=False,
        deleted_at=now - dt.timedelta(days=31), deletion_scheduled_at=now - dt.timedelta(days=1),
    )
    not_due_email = await _create_user(
        pg_engine, is_active=False,
        deleted_at=now - dt.timedelta(days=2), deletion_scheduled_at=now + dt.timedelta(days=28),
    )
    active_email = await _create_user(pg_engine)  # never soft-deleted, deletion_scheduled_at is None

    try:
        purged_count = purge_deleted_accounts.apply().get()
        assert purged_count >= 1  # the shared dev DB may have other overdue rows too; assert at least ours

        assert not await _exists(pg_engine, overdue_email)
        assert await _exists(pg_engine, not_due_email)
        assert await _exists(pg_engine, active_email)
    finally:
        async with pg_engine.begin() as conn:
            await conn.execute(delete(User).where(User.email.in_([overdue_email, not_due_email, active_email])))


async def test_purge_task_is_idempotent(pg_engine):
    first_run = purge_deleted_accounts.apply().get()
    second_run = purge_deleted_accounts.apply().get()
    assert second_run == 0  # nothing new became overdue between the two calls
    assert first_run >= 0


async def test_purge_task_deletes_the_orphaned_avatar_from_storage(pg_engine):
    """The fix for the previously-documented gap: purging a soft-deleted
    account must not leave its avatar image sitting in the bucket
    forever. Uploads a real avatar, backdates the account past its grace
    window, runs the real purge task, then confirms the S3 object is
    genuinely gone (not just that the DB row was deleted)."""
    if not (settings.S3_BUCKET_NAME and settings.S3_ACCESS_KEY_ID and settings.S3_SECRET_ACCESS_KEY):
        pytest.skip("S3_* env vars are not configured -- skipping the orphaned-avatar purge test")

    s3_client = boto3.client(
        "s3", endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        region_name=settings.S3_REGION,
    )

    now = dt.datetime.now(dt.timezone.utc)
    user_id = uuid.uuid4()
    png_bytes = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c626001000000050001a5f645400000000049454e44ae426082"
    )
    avatar_url = upload_avatar(user_id, png_bytes)
    avatar_key = avatar_url.split(f"/public/{settings.S3_BUCKET_NAME}/", 1)[1]

    email = f"celery-purge-avatar-{uuid.uuid4().hex[:10]}@example.com"
    async with pg_engine.begin() as conn:
        await conn.execute(User.__table__.insert().values(
            id=user_id, email=email, hashed_password="irrelevant", is_active=False,
            avatar_url=avatar_url, deleted_at=now - dt.timedelta(days=31), deletion_scheduled_at=now - dt.timedelta(days=1),
        ))

    try:
        # The object exists before the purge runs -- otherwise the
        # "it's gone afterwards" assertion below would be meaningless.
        s3_client.head_object(Bucket=settings.S3_BUCKET_NAME, Key=avatar_key)

        purge_deleted_accounts.apply().get()

        with pytest.raises(ClientError):
            s3_client.head_object(Bucket=settings.S3_BUCKET_NAME, Key=avatar_key)
    finally:
        async with pg_engine.begin() as conn:
            await conn.execute(delete(User).where(User.email == email))
        try:
            s3_client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=avatar_key)  # no-op if the purge already removed it
        except ClientError:
            pass

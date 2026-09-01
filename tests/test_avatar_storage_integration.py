"""
1.1.13 avatar upload, tested against the REAL S3-compatible bucket in
S3_* env vars (Supabase Storage's S3 API in dev). Skips if not configured,
same pattern as the Postgres/Celery integration tests.
"""

import uuid

import boto3
import pytest
import pytest_asyncio
from botocore.exceptions import ClientError
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import create_async_engine

from api.config import settings
from api.main import app
from api.models.user import User

# Builds its own engine rather than importing api.database's singleton --
# see test_postgres_integration.py's docstring for why: asyncpg connections
# are bound to the event loop they were opened on, and pytest-asyncio's
# per-test loops make reusing a module-level singleton across fixtures
# fail unpredictably.
pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest.fixture(scope="module")
async def pg_engine():
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"DATABASE_URL is not reachable -- skipping avatar storage integration tests ({exc})")
    yield engine
    await engine.dispose()

# A minimal valid 1x1 transparent PNG -- real image bytes, not a placeholder
# string, so content-type/magic-byte handling is exercised for real.
PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c626001000000050001a5f645400000000049454e44ae426082"
)


@pytest.fixture(scope="module")
def s3_client():
    if not (settings.S3_BUCKET_NAME and settings.S3_ACCESS_KEY_ID and settings.S3_SECRET_ACCESS_KEY):
        pytest.skip("S3_* env vars are not configured -- skipping avatar storage integration tests")
    client = boto3.client(
        "s3", endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        region_name=settings.S3_REGION,
    )
    try:
        client.list_objects_v2(Bucket=settings.S3_BUCKET_NAME, MaxKeys=1)
    except ClientError as exc:
        pytest.skip(f"S3 bucket is not reachable -- skipping avatar storage integration tests ({exc})")
    return client


@pytest_asyncio.fixture(loop_scope="module")
async def registered_user_token(pg_engine):
    """A real user via the real Postgres DB (app's own get_db, no
    dependency override) -- avatar upload needs a persisted user row to
    attach avatar_url to. Cleanup uses pg_engine, not the app's own
    singleton, for the same event-loop reason noted above."""
    email = f"avatar-itest-{uuid.uuid4().hex[:10]}@example.com"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        register = await client.post("/auth/register", json={
            "email": email, "password": "correct-horse-battery-staple",
            "full_name": "Avatar Integration Test", "accept_terms": True,
        })
        yield client, register.json()["access_token"]

    async with pg_engine.begin() as conn:
        await conn.execute(delete(User).where(User.email == email))


def _key_from_url(url: str) -> str:
    # https://.../object/public/<bucket>/<key...>
    return url.split(f"/public/{settings.S3_BUCKET_NAME}/", 1)[1]


async def test_avatar_upload_rejects_disallowed_content_type(registered_user_token, s3_client):
    client, token = registered_user_token
    response = await client.post(
        "/account/avatar", headers={"Authorization": f"Bearer {token}"},
        files={"file": ("payload.txt", b"not an image", "text/plain")},
    )
    assert response.status_code == 400


async def test_avatar_upload_rejects_oversized_file(registered_user_token, s3_client):
    client, token = registered_user_token
    oversized = b"\x00" * (5 * 1024 * 1024 + 1)
    response = await client.post(
        "/account/avatar", headers={"Authorization": f"Bearer {token}"},
        files={"file": ("big.png", oversized, "image/png")},
    )
    assert response.status_code == 400


async def test_avatar_upload_stores_object_and_is_publicly_fetchable(registered_user_token, s3_client):
    client, token = registered_user_token
    keys_to_clean = []

    try:
        upload = await client.post(
            "/account/avatar", headers={"Authorization": f"Bearer {token}"},
            files={"file": ("avatar.png", PNG_BYTES, "image/png")},
        )
        assert upload.status_code == 200
        url = upload.json()["avatar_url"]
        key = _key_from_url(url)
        keys_to_clean.append(key)

        # Confirm the object genuinely exists in the bucket (not just that
        # boto3's put_object call didn't raise).
        head = s3_client.head_object(Bucket=settings.S3_BUCKET_NAME, Key=key)
        assert head["ContentLength"] == len(PNG_BYTES)

        me = await client.get("/account/me", headers={"Authorization": f"Bearer {token}"})
        assert me.json()["avatar_url"] == url
    finally:
        for key in keys_to_clean:
            s3_client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=key)


async def test_avatar_upload_replaces_previous_avatar(registered_user_token, s3_client):
    client, token = registered_user_token
    keys_to_clean = []

    try:
        first = await client.post(
            "/account/avatar", headers={"Authorization": f"Bearer {token}"},
            files={"file": ("first.png", PNG_BYTES, "image/png")},
        )
        first_url = first.json()["avatar_url"]
        keys_to_clean.append(_key_from_url(first_url))

        second = await client.post(
            "/account/avatar", headers={"Authorization": f"Bearer {token}"},
            files={"file": ("second.png", PNG_BYTES, "image/png")},
        )
        second_url = second.json()["avatar_url"]
        keys_to_clean.append(_key_from_url(second_url))

        # A fresh random key per upload (not a fixed user_id.png) -- old
        # CDN/browser caches never serve a stale avatar under a reused URL.
        assert second_url != first_url

        me = await client.get("/account/me", headers={"Authorization": f"Bearer {token}"})
        assert me.json()["avatar_url"] == second_url
    finally:
        for key in keys_to_clean:
            s3_client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=key)


async def test_avatar_upload_requires_credentials(registered_user_token, s3_client):
    client, _token = registered_user_token
    response = await client.post("/account/avatar", files={"file": ("avatar.png", PNG_BYTES, "image/png")})
    assert response.status_code in (401, 403)

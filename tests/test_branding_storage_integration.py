"""
Partie 1.3.10 logo/favicon upload, tested against the REAL S3-compatible
bucket in S3_* env vars (the same "avatars" bucket 1.1.13's avatar
upload already uses, under a branding/ key prefix -- see
api/services/storage.py's module docstring for why no second bucket).
Skips if not configured, same pattern as
tests/test_avatar_storage_integration.py and the Postgres/Celery
integration tests.
"""

import io
import uuid

import boto3
import pytest
import pytest_asyncio
from botocore.exceptions import ClientError
from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import create_async_engine

from api.config import settings
from api.main import app
from api.models.organization import Organization
from api.models.user import User


@pytest.fixture(scope="module")
async def pg_engine():
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"DATABASE_URL is not reachable -- skipping branding storage integration tests ({exc})")
    yield engine
    await engine.dispose()


@pytest.fixture(scope="module")
def s3_client():
    if not (settings.S3_BUCKET_NAME and settings.S3_ACCESS_KEY_ID and settings.S3_SECRET_ACCESS_KEY):
        pytest.skip("S3_* env vars are not configured -- skipping branding storage integration tests")
    client = boto3.client(
        "s3", endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        region_name=settings.S3_REGION,
    )
    try:
        client.list_objects_v2(Bucket=settings.S3_BUCKET_NAME, MaxKeys=1)
    except ClientError as exc:
        pytest.skip(f"S3 bucket is not reachable -- skipping branding storage integration tests ({exc})")
    return client


def _png_bytes(width: int, height: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color=(37, 99, 235)).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest_asyncio.fixture
async def owner_client_and_org(pg_engine):
    """A real user + organization via the real Postgres DB (app's own
    get_db, no dependency override) -- branding upload needs a
    persisted organization row to attach logo_url/favicon_url to."""
    email = f"branding-itest-{uuid.uuid4().hex[:10]}@example.com"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        register = await client.post("/auth/register", json={
            "email": email, "password": "correct-horse-battery-staple",
            "full_name": "Branding Integration Test", "accept_terms": True,
        })
        token = register.json()["access_token"]
        org = await client.post("/organizations", json={"name": "Branding ITest Org"}, headers={"Authorization": f"Bearer {token}"})
        org_id = org.json()["id"]
        yield client, token, org_id

    async with pg_engine.begin() as conn:
        await conn.execute(delete(Organization).where(Organization.id == uuid.UUID(org_id)))
        await conn.execute(delete(User).where(User.email == email))


def _key_from_url(url: str) -> str:
    return url.split(f"/public/{settings.S3_BUCKET_NAME}/", 1)[1]


async def test_logo_upload_stores_object_and_is_publicly_fetchable(owner_client_and_org, s3_client):
    client, token, org_id = owner_client_and_org
    keys_to_clean = []

    try:
        logo_bytes = _png_bytes(64, 64)
        upload = await client.post(
            f"/organizations/{org_id}/branding/logo", headers={"Authorization": f"Bearer {token}"},
            files={"file": ("logo.png", logo_bytes, "image/png")},
        )
        assert upload.status_code == 200, upload.text
        url = upload.json()["logo_url"]
        key = _key_from_url(url)
        keys_to_clean.append(key)
        assert key.startswith(f"branding/{org_id}/logo-")

        head = s3_client.head_object(Bucket=settings.S3_BUCKET_NAME, Key=key)
        assert head["ContentLength"] == len(logo_bytes)

        branding = await client.get(f"/organizations/{org_id}/branding")
        assert branding.json()["logo_url"] == url
    finally:
        for key in keys_to_clean:
            s3_client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=key)


async def test_logo_upload_replaces_and_deletes_the_previous_object(owner_client_and_org, s3_client):
    client, token, org_id = owner_client_and_org
    keys_to_clean = []

    try:
        first = await client.post(
            f"/organizations/{org_id}/branding/logo", headers={"Authorization": f"Bearer {token}"},
            files={"file": ("first.png", _png_bytes(32, 32), "image/png")},
        )
        first_url = first.json()["logo_url"]
        first_key = _key_from_url(first_url)

        second = await client.post(
            f"/organizations/{org_id}/branding/logo", headers={"Authorization": f"Bearer {token}"},
            files={"file": ("second.png", _png_bytes(32, 32), "image/png")},
        )
        second_url = second.json()["logo_url"]
        keys_to_clean.append(_key_from_url(second_url))

        assert second_url != first_url

        # The FIRST object must genuinely be gone -- not just replaced
        # in the database column, actually deleted from the bucket.
        try:
            s3_client.head_object(Bucket=settings.S3_BUCKET_NAME, Key=first_key)
            assert False, "previous logo object should have been deleted from storage"
        except ClientError as exc:
            assert exc.response["Error"]["Code"] in ("404", "NoSuchKey")
    finally:
        for key in keys_to_clean:
            s3_client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=key)


async def test_deleting_a_logo_removes_it_from_storage(owner_client_and_org, s3_client):
    client, token, org_id = owner_client_and_org

    upload = await client.post(
        f"/organizations/{org_id}/branding/logo", headers={"Authorization": f"Bearer {token}"},
        files={"file": ("logo.png", _png_bytes(32, 32), "image/png")},
    )
    key = _key_from_url(upload.json()["logo_url"])

    delete_response = await client.delete(f"/organizations/{org_id}/branding/logo", headers={"Authorization": f"Bearer {token}"})
    assert delete_response.status_code == 200
    assert delete_response.json()["logo_url"] is None

    try:
        s3_client.head_object(Bucket=settings.S3_BUCKET_NAME, Key=key)
        assert False, "deleted logo object should no longer exist in storage"
    except ClientError as exc:
        assert exc.response["Error"]["Code"] in ("404", "NoSuchKey")


async def test_favicon_upload_stores_object_under_its_own_dimension_limit(owner_client_and_org, s3_client):
    client, token, org_id = owner_client_and_org
    keys_to_clean = []

    try:
        favicon_bytes = _png_bytes(48, 48)
        upload = await client.post(
            f"/organizations/{org_id}/branding/favicon", headers={"Authorization": f"Bearer {token}"},
            files={"file": ("favicon.png", favicon_bytes, "image/png")},
        )
        assert upload.status_code == 200, upload.text
        url = upload.json()["favicon_url"]
        key = _key_from_url(url)
        keys_to_clean.append(key)
        assert key.startswith(f"branding/{org_id}/favicon-")
    finally:
        for key in keys_to_clean:
            s3_client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=key)


async def test_favicon_upload_rejects_an_image_too_large_for_a_favicon(owner_client_and_org, s3_client):
    client, token, org_id = owner_client_and_org

    oversized = _png_bytes(600, 600)  # exceeds MAX_FAVICON_DIMENSION_PX (512), fine for a logo
    response = await client.post(
        f"/organizations/{org_id}/branding/favicon", headers={"Authorization": f"Bearer {token}"},
        files={"file": ("toobig.png", oversized, "image/png")},
    )
    assert response.status_code == 400
    assert "dimensions" in response.json()["detail"]


async def test_logo_upload_requires_credentials(owner_client_and_org, s3_client):
    client, _token, org_id = owner_client_and_org
    response = await client.post(f"/organizations/{org_id}/branding/logo", files={"file": ("logo.png", _png_bytes(32, 32), "image/png")})
    assert response.status_code in (401, 403)

"""Partie 22 -- real upload, validation, list/get/delete, and access
control for standalone media (audio/video/top-level image). S3 is
stubbed the same way tests/test_documents.py's own `_stub_s3` does
(a plain monkeypatched fake, not moto) -- these tests care about real
validation/DB/access-control behavior, not the real S3 wire protocol
itself."""

import io
import uuid

import pytest
from sqlalchemy import select

from api.config import settings
from api.models.media import MediaAsset
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _make_org(client, db_session, register_payload, name):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_id = (await client.post("/organizations", json={"name": name}, headers=_auth_header(owner_token))).json()["id"]
    return owner_token, org_id


def _stub_storage(monkeypatch):
    monkeypatch.setattr("api.services.media.upload_media_file", lambda org_id, asset_id, filename, content, mime_type: f"media/{org_id}/{asset_id}/{filename}")
    monkeypatch.setattr("api.services.media.download_document_file", lambda file_key: b"fake-bytes-for-tests")
    monkeypatch.setattr("api.services.media.delete_document_file", lambda file_key: None)


def _stub_processing(monkeypatch):
    """Real upload tests don't need real processing to actually run
    (that's covered by tests/backend/media/test_media_processing.py) --
    the Celery dispatch is best-effort and swallows any broker error,
    so simply not having a real broker reachable in tests is already
    the honest, real behavior; nothing to stub for upload-only tests."""


_PNG_MAGIC_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


async def test_upload_image_creates_a_pending_asset(client, db_session, register_payload, monkeypatch):
    _stub_storage(monkeypatch)
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Media Org")

    response = await client.post(
        f"/organizations/{org_id}/media", files={"file": ("photo.png", io.BytesIO(_PNG_MAGIC_BYTES), "image/png")},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["media_type"] == "image"
    assert body["filename"] == "photo.png"


async def test_upload_rejects_unsupported_mime_type(client, db_session, register_payload, monkeypatch):
    _stub_storage(monkeypatch)
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Reject Org")

    response = await client.post(
        f"/organizations/{org_id}/media", files={"file": ("doc.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 400


async def test_upload_rejects_oversized_image(client, db_session, register_payload, monkeypatch):
    _stub_storage(monkeypatch)
    monkeypatch.setattr(settings, "MULTIMODAL_MAX_IMAGE_SIZE_MB", 0)  # any real bytes now exceed the real limit
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Oversize Org")

    response = await client.post(
        f"/organizations/{org_id}/media", files={"file": ("photo.png", io.BytesIO(_PNG_MAGIC_BYTES), "image/png")},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 400


async def test_upload_disabled_when_multimodal_disabled(client, db_session, register_payload, monkeypatch):
    _stub_storage(monkeypatch)
    monkeypatch.setattr(settings, "MULTIMODAL_ENABLED", False)
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Disabled Org")

    response = await client.post(
        f"/organizations/{org_id}/media", files={"file": ("photo.png", io.BytesIO(_PNG_MAGIC_BYTES), "image/png")},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 400


async def test_list_media_scoped_to_own_organization(client, db_session, register_payload, monkeypatch):
    _stub_storage(monkeypatch)
    owner_token, org_id = await _make_org(client, db_session, register_payload, "List Org")
    await client.post(f"/organizations/{org_id}/media", files={"file": ("a.png", io.BytesIO(_PNG_MAGIC_BYTES), "image/png")}, headers=_auth_header(owner_token))

    other_token, other_org_id = await _register(client, db_session, "other_media_org_owner@example.com")
    other_org_id = (await client.post("/organizations", json={"name": "Other Org"}, headers=_auth_header(other_token))).json()["id"]

    response = await client.get(f"/organizations/{org_id}/media", headers=_auth_header(owner_token))
    assert response.json()["total"] == 1

    response = await client.get(f"/organizations/{other_org_id}/media", headers=_auth_header(other_token))
    assert response.json()["total"] == 0


async def test_get_media_returns_404_for_non_member(client, db_session, register_payload, monkeypatch):
    _stub_storage(monkeypatch)
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Private Org")
    created = (await client.post(f"/organizations/{org_id}/media", files={"file": ("a.png", io.BytesIO(_PNG_MAGIC_BYTES), "image/png")}, headers=_auth_header(owner_token))).json()

    stranger_token, _stranger = await _register(client, db_session, "stranger_media@example.com")
    response = await client.get(f"/media/{created['id']}", headers=_auth_header(stranger_token))
    assert response.status_code == 404


async def test_viewer_cannot_delete_media(client, db_session, register_payload, monkeypatch):
    _stub_storage(monkeypatch)
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Viewer Org")
    created = (await client.post(f"/organizations/{org_id}/media", files={"file": ("a.png", io.BytesIO(_PNG_MAGIC_BYTES), "image/png")}, headers=_auth_header(owner_token))).json()

    viewer_token, viewer = await _register(client, db_session, "media_viewer@example.com")
    owner = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    db_session.add(OrganizationMember(organization_id=uuid.UUID(org_id), user_id=viewer.id, role=OrganizationRole.viewer, invited_by=owner.id))
    await db_session.commit()

    response = await client.delete(f"/media/{created['id']}", headers=_auth_header(viewer_token))
    assert response.status_code == 403


async def test_delete_media_removes_the_row(client, db_session, register_payload, monkeypatch):
    _stub_storage(monkeypatch)
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Delete Org")
    created = (await client.post(f"/organizations/{org_id}/media", files={"file": ("a.png", io.BytesIO(_PNG_MAGIC_BYTES), "image/png")}, headers=_auth_header(owner_token))).json()

    response = await client.delete(f"/media/{created['id']}", headers=_auth_header(owner_token))
    assert response.status_code == 204
    assert await db_session.get(MediaAsset, uuid.UUID(created["id"])) is None

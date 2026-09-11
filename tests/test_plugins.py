"""Partie 16 (ter) -- plugin marketplace: manifest validation, static
code security scan, publish/approve/reject/suspend, install/uninstall,
reviews. S3 is mocked (boto3's put_object/get_object) -- no real
network call belongs in this suite, same reasoning as every other
storage-backed test file (see tests/test_storage.py)."""

import io
import json
import uuid
from unittest.mock import MagicMock

import pytest


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register_and_create_org(client, register_payload):
    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    org_id = (await client.post("/organizations", json={"name": "Plugin Org"}, headers=_auth_header(token))).json()["id"]
    return token, org_id


def _valid_manifest(**overrides) -> dict:
    manifest = {
        "name": "My Plugin", "version": "1.0.0", "entry_point": "index.js",
        "description": "A real test plugin.", "permissions": ["read_documents"],
    }
    manifest.update(overrides)
    return manifest


def _files(manifest: dict, code: bytes = b"console.log('hello');"):
    return {
        "manifest": ("manifest.json", io.BytesIO(json.dumps(manifest).encode()), "application/json"),
        "code": ("index.js", io.BytesIO(code), "text/javascript"),
    }


@pytest.fixture(autouse=True)
def _mock_s3(monkeypatch):
    from api.services import plugins

    store: dict[str, bytes] = {}

    def fake_client():
        client = MagicMock()

        def put_object(Bucket, Key, Body, ContentType):
            store[Key] = Body

        def get_object(Bucket, Key):
            return {"Body": io.BytesIO(store[Key])}

        client.put_object.side_effect = put_object
        client.get_object.side_effect = get_object
        return client

    monkeypatch.setattr(plugins, "_s3_client", fake_client)
    return store


# --------------------------------------------------------------------- Unit


def test_validate_manifest_rejects_missing_field():
    from api.security.plugin_manifest import PluginManifestError, validate_manifest

    with pytest.raises(PluginManifestError):
        validate_manifest({"name": "x"}, slug="x")


def test_validate_manifest_rejects_unknown_permission():
    from api.security.plugin_manifest import PluginManifestError, validate_manifest

    with pytest.raises(PluginManifestError):
        validate_manifest(_valid_manifest(permissions=["delete_everything"]), slug="my-plugin")


def test_validate_manifest_rejects_bad_version():
    from api.security.plugin_manifest import PluginManifestError, validate_manifest

    with pytest.raises(PluginManifestError):
        validate_manifest(_valid_manifest(version="not-semver"), slug="my-plugin")


def test_validate_manifest_accepts_a_real_valid_manifest():
    from api.security.plugin_manifest import validate_manifest

    validate_manifest(_valid_manifest(), slug="my-plugin")  # does not raise


def test_scan_plugin_code_rejects_eval():
    from api.security.plugin_manifest import PluginCodeSecurityError, scan_plugin_code

    with pytest.raises(PluginCodeSecurityError):
        scan_plugin_code(b"eval(userInput)")


def test_scan_plugin_code_rejects_child_process():
    from api.security.plugin_manifest import PluginCodeSecurityError, scan_plugin_code

    with pytest.raises(PluginCodeSecurityError):
        scan_plugin_code(b"const cp = require('child_process');")


def test_scan_plugin_code_rejects_oversized_upload():
    from api.security.plugin_manifest import MAX_PLUGIN_CODE_BYTES, PluginCodeSecurityError, scan_plugin_code

    with pytest.raises(PluginCodeSecurityError):
        scan_plugin_code(b"x" * (MAX_PLUGIN_CODE_BYTES + 1))


def test_scan_plugin_code_accepts_clean_code():
    from api.security.plugin_manifest import scan_plugin_code

    scan_plugin_code(b"console.log('hello world');")  # does not raise


# ---------------------------------------------------------------------- Endpoints


async def test_publish_plugin_creates_pending_plugin(client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    response = await client.post(
        f"/organizations/{org_id}/plugins/publish", data={"name": "My Plugin", "description": "A real test plugin."},
        files=_files(_valid_manifest()), headers=_auth_header(token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["slug"] == "my-plugin"


async def test_publish_plugin_rejects_dangerous_code(client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    response = await client.post(
        f"/organizations/{org_id}/plugins/publish", data={"name": "Evil Plugin", "description": "..."},
        files=_files(_valid_manifest(name="Evil Plugin"), code=b"eval(userInput)"), headers=_auth_header(token),
    )
    assert response.status_code == 400


async def test_unapproved_plugin_is_not_in_marketplace_listing(client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    await client.post(
        f"/organizations/{org_id}/plugins/publish", data={"name": "Hidden Plugin", "description": "..."},
        files=_files(_valid_manifest(name="Hidden Plugin")), headers=_auth_header(token),
    )
    listing = await client.get("/marketplace/plugins")
    assert listing.json() == []


async def test_approve_plugin_makes_it_visible_in_marketplace(client, db_session, register_payload):
    from sqlalchemy import select

    from api.models.user import User, UserRole

    token, org_id = await _register_and_create_org(client, register_payload)
    created = await client.post(
        f"/organizations/{org_id}/plugins/publish", data={"name": "Real Plugin", "description": "..."},
        files=_files(_valid_manifest(name="Real Plugin")), headers=_auth_header(token),
    )
    plugin_id = created.json()["id"]

    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    user.role = UserRole.superadmin
    await db_session.commit()

    approved = await client.post(f"/admin/plugins/{plugin_id}/approve", headers=_auth_header(token))
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    listing = await client.get("/marketplace/plugins")
    assert len(listing.json()) == 1


async def test_reject_plugin_records_reason(client, db_session, register_payload):
    from sqlalchemy import select

    from api.models.user import User, UserRole

    token, org_id = await _register_and_create_org(client, register_payload)
    created = await client.post(
        f"/organizations/{org_id}/plugins/publish", data={"name": "Bad Plugin", "description": "..."},
        files=_files(_valid_manifest(name="Bad Plugin")), headers=_auth_header(token),
    )
    plugin_id = created.json()["id"]

    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    user.role = UserRole.superadmin
    await db_session.commit()

    rejected = await client.post(f"/admin/plugins/{plugin_id}/reject", json={"reason": "Does not meet quality bar"}, headers=_auth_header(token))
    assert rejected.status_code == 200
    assert rejected.json()["rejection_reason"] == "Does not meet quality bar"


async def test_install_requires_approved_status(client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    created = await client.post(
        f"/organizations/{org_id}/plugins/publish", data={"name": "Unreviewed Plugin", "description": "..."},
        files=_files(_valid_manifest(name="Unreviewed Plugin")), headers=_auth_header(token),
    )
    plugin_id = created.json()["id"]

    response = await client.post(f"/organizations/{org_id}/plugins/{plugin_id}/install", headers=_auth_header(token))
    assert response.status_code == 400


async def test_install_and_uninstall_flow(client, db_session, register_payload):
    from sqlalchemy import select

    from api.models.user import User, UserRole

    token, org_id = await _register_and_create_org(client, register_payload)
    created = await client.post(
        f"/organizations/{org_id}/plugins/publish", data={"name": "Installable Plugin", "description": "..."},
        files=_files(_valid_manifest(name="Installable Plugin")), headers=_auth_header(token),
    )
    plugin_id = created.json()["id"]

    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    user.role = UserRole.superadmin
    await db_session.commit()
    await client.post(f"/admin/plugins/{plugin_id}/approve", headers=_auth_header(token))

    installed = await client.post(f"/organizations/{org_id}/plugins/{plugin_id}/install", headers=_auth_header(token))
    assert installed.status_code == 201
    installation_id = installed.json()["id"]

    duplicate = await client.post(f"/organizations/{org_id}/plugins/{plugin_id}/install", headers=_auth_header(token))
    assert duplicate.status_code == 409

    listing = await client.get(f"/organizations/{org_id}/plugins/installed", headers=_auth_header(token))
    assert len(listing.json()) == 1

    disabled = await client.patch(f"/organizations/{org_id}/plugins/installed/{installation_id}", json={"enabled": False}, headers=_auth_header(token))
    assert disabled.json()["enabled"] is False

    uninstalled = await client.delete(f"/organizations/{org_id}/plugins/installed/{installation_id}", headers=_auth_header(token))
    assert uninstalled.status_code == 204

    listing_after = await client.get(f"/organizations/{org_id}/plugins/installed", headers=_auth_header(token))
    assert listing_after.json() == []


async def test_submit_review_and_rating_summary(client, db_session, register_payload):
    from sqlalchemy import select

    from api.models.user import User, UserRole

    token, org_id = await _register_and_create_org(client, register_payload)
    created = await client.post(
        f"/organizations/{org_id}/plugins/publish", data={"name": "Reviewed Plugin", "description": "..."},
        files=_files(_valid_manifest(name="Reviewed Plugin")), headers=_auth_header(token),
    )
    plugin_id = created.json()["id"]

    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    user.role = UserRole.superadmin
    await db_session.commit()
    await client.post(f"/admin/plugins/{plugin_id}/approve", headers=_auth_header(token))

    review = await client.post(f"/organizations/{org_id}/plugins/{plugin_id}/reviews", json={"rating": 4, "comment": "Pretty good"}, headers=_auth_header(token))
    assert review.status_code == 201

    # Re-reviewing the SAME plugin as the SAME user updates in place, not a second row.
    updated_review = await client.post(f"/organizations/{org_id}/plugins/{plugin_id}/reviews", json={"rating": 5, "comment": "Actually great"}, headers=_auth_header(token))
    assert updated_review.status_code == 201

    reviews = await client.get(f"/marketplace/plugins/{plugin_id}/reviews")
    assert len(reviews.json()) == 1
    assert reviews.json()[0]["rating"] == 5

    summary = await client.get(f"/marketplace/plugins/{plugin_id}/rating")
    assert summary.json() == {"average_rating": 5.0, "review_count": 1}


async def test_submit_review_rejects_invalid_rating(client, db_session, register_payload):
    from sqlalchemy import select

    from api.models.user import User, UserRole

    token, org_id = await _register_and_create_org(client, register_payload)
    created = await client.post(
        f"/organizations/{org_id}/plugins/publish", data={"name": "Rating Bounds Plugin", "description": "..."},
        files=_files(_valid_manifest(name="Rating Bounds Plugin")), headers=_auth_header(token),
    )
    plugin_id = created.json()["id"]

    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    user.role = UserRole.superadmin
    await db_session.commit()
    await client.post(f"/admin/plugins/{plugin_id}/approve", headers=_auth_header(token))

    response = await client.post(f"/organizations/{org_id}/plugins/{plugin_id}/reviews", json={"rating": 9}, headers=_auth_header(token))
    assert response.status_code == 400


async def test_list_permissions_returns_the_static_catalog(client):
    response = await client.get("/marketplace/permissions")
    assert response.status_code == 200
    ids = {p["id"] for p in response.json()}
    assert "read_documents" in ids

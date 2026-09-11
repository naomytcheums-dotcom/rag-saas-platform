"""Partie 16 (ter) -- shared real helpers for tests/test_plugins.py,
tests/test_plugin_marketplace.py, tests/test_plugin_reviews.py, and
tests/test_plugin_sandbox.py. Not itself a test file (no test_
prefix -- pytest does not collect it)."""

import io
import json
from unittest.mock import MagicMock


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register_and_create_org(client, register_payload):
    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    org_id = (await client.post("/organizations", json={"name": "Plugin Org"}, headers=_auth_header(token))).json()["id"]
    return token, org_id


async def _promote_to_superadmin(db_session, email: str):
    from sqlalchemy import select

    from api.models.user import User, UserRole

    user = await db_session.scalar(select(User).where(User.email == email))
    user.role = UserRole.superadmin
    await db_session.commit()


def _valid_manifest(**overrides) -> dict:
    manifest = {
        "name": "My Plugin", "version": "1.0.0", "entry_point": "index.js",
        "description": "A real test plugin.", "permissions": ["read:documents"],
    }
    manifest.update(overrides)
    return manifest


def _files(manifest: dict, code: bytes = b"console.log('hello');"):
    return {
        "manifest": ("manifest.json", io.BytesIO(json.dumps(manifest).encode()), "application/json"),
        "code": ("index.js", io.BytesIO(code), "text/javascript"),
    }


def _mock_s3_fixture(monkeypatch):
    """A real, in-memory fake of the two boto3 calls this module's own
    service layer uses (put_object/get_object) -- no real S3/network
    call belongs in this suite, same reasoning as every other storage-
    backed test file (tests/test_storage.py). Used as an autouse
    fixture in each plugin test file via `_mock_s3 =
    pytest.fixture(autouse=True)(_mock_s3_fixture)`."""
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


async def _publish_and_approve(client, db_session, register_payload, *, name: str, manifest_overrides: dict | None = None, code: bytes = b"console.log('hello');"):
    """Real, shared setup: publish a plugin, promote its publisher to
    superadmin, approve it -- the common prerequisite for install/
    review/execute tests, not duplicated 6 times across test files."""
    token, org_id = await _register_and_create_org(client, register_payload)
    manifest = _valid_manifest(name=name, **(manifest_overrides or {}))
    created = await client.post(
        f"/organizations/{org_id}/plugins/publish", data={"name": name, "description": f"{name} description"},
        files=_files(manifest, code=code), headers=_auth_header(token),
    )
    plugin_id = created.json()["id"]
    await _promote_to_superadmin(db_session, register_payload["email"])
    approved = await client.post(f"/admin/plugins/{plugin_id}/approve", headers=_auth_header(token))
    assert approved.status_code == 200
    return token, org_id, plugin_id

"""Partie 16 (ter) -- plugin publishing/versioning/moderation: manifest
validation, static code security scan, publish/republish (real
versioning via PluginVersion), approve/reject/suspend. S3 is mocked
(boto3's put_object/get_object) -- no real network call belongs in
this suite, same reasoning as every other storage-backed test file
(see tests/test_storage.py). Installation/uninstallation and search/
filter/sort live in tests/test_plugin_marketplace.py; reviews in
tests/test_plugin_reviews.py; real sandboxed execution in
tests/test_plugin_sandbox.py -- one file per concern, same split this
project used for Partie 15's own connections/mappings/webhooks/
transformations (this project's real, flat tests/ convention, not the
literal spec's tests/backend/plugins/ subdirectory -- kept consistent
with every one of this repo's 200+ other test files)."""

import uuid

import pytest

from plugin_test_helpers import _auth_header, _files, _mock_s3_fixture, _promote_to_superadmin, _publish_and_approve, _register_and_create_org, _valid_manifest

_mock_s3 = pytest.fixture(autouse=True)(_mock_s3_fixture)


# --------------------------------------------------------------------- Unit

def test_validate_manifest_rejects_missing_field():
    from api.security.plugin_manifest import PluginManifestError, validate_manifest

    with pytest.raises(PluginManifestError):
        validate_manifest({"name": "x"}, slug="x")


def test_validate_manifest_rejects_unknown_permission():
    from api.security.plugin_manifest import PluginManifestError, validate_manifest

    with pytest.raises(PluginManifestError):
        validate_manifest(_valid_manifest(permissions=["delete:everything"]), slug="my-plugin")


def test_validate_manifest_rejects_unknown_hook():
    from api.security.plugin_manifest import PluginManifestError, validate_manifest

    with pytest.raises(PluginManifestError):
        validate_manifest(_valid_manifest(hooks=["on_not_a_real_hook"]), slug="my-plugin")


def test_validate_manifest_accepts_declared_hooks():
    from api.security.plugin_manifest import validate_manifest

    validate_manifest(_valid_manifest(hooks=["on_document_uploaded"]), slug="my-plugin")  # does not raise


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


# ---------------------------------------------------------------------- Publish/moderation endpoints

async def test_publish_plugin_creates_pending_plugin(client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    response = await client.post(
        f"/organizations/{org_id}/plugins/publish", data={"name": "My Plugin", "description": "A real test plugin.", "category": "productivity"},
        files=_files(_valid_manifest()), headers=_auth_header(token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["slug"] == "my-plugin"
    assert body["category"] == "productivity"
    assert body["install_count"] == 0


async def test_publish_plugin_rejects_dangerous_code(client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    response = await client.post(
        f"/organizations/{org_id}/plugins/publish", data={"name": "Evil Plugin", "description": "..."},
        files=_files(_valid_manifest(name="Evil Plugin"), code=b"eval(userInput)"), headers=_auth_header(token),
    )
    assert response.status_code == 400


async def test_approve_plugin_makes_it_visible_in_marketplace(client, db_session, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    created = await client.post(
        f"/organizations/{org_id}/plugins/publish", data={"name": "Real Plugin", "description": "..."},
        files=_files(_valid_manifest(name="Real Plugin")), headers=_auth_header(token),
    )
    plugin_id = created.json()["id"]
    await _promote_to_superadmin(db_session, register_payload["email"])

    approved = await client.post(f"/admin/plugins/{plugin_id}/approve", headers=_auth_header(token))
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    listing = await client.get("/marketplace/plugins")
    assert len(listing.json()) == 1


async def test_reject_plugin_records_reason(client, db_session, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    created = await client.post(
        f"/organizations/{org_id}/plugins/publish", data={"name": "Bad Plugin", "description": "..."},
        files=_files(_valid_manifest(name="Bad Plugin")), headers=_auth_header(token),
    )
    plugin_id = created.json()["id"]
    await _promote_to_superadmin(db_session, register_payload["email"])

    rejected = await client.post(f"/admin/plugins/{plugin_id}/reject", json={"reason": "Does not meet quality bar"}, headers=_auth_header(token))
    assert rejected.status_code == 200
    assert rejected.json()["rejection_reason"] == "Does not meet quality bar"


async def test_suspend_plugin_does_not_remove_existing_installations(client, db_session, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    created = await client.post(
        f"/organizations/{org_id}/plugins/publish", data={"name": "Suspendable Plugin", "description": "..."},
        files=_files(_valid_manifest(name="Suspendable Plugin")), headers=_auth_header(token),
    )
    plugin_id = created.json()["id"]
    await _promote_to_superadmin(db_session, register_payload["email"])
    await client.post(f"/admin/plugins/{plugin_id}/approve", headers=_auth_header(token))
    await client.post(f"/organizations/{org_id}/plugins/{plugin_id}/install", headers=_auth_header(token))

    suspended = await client.post(f"/admin/plugins/{plugin_id}/suspend", json={"reason": "Policy violation"}, headers=_auth_header(token))
    assert suspended.status_code == 200
    assert suspended.json()["status"] == "suspended"

    installed = await client.get(f"/organizations/{org_id}/plugins/installed", headers=_auth_header(token))
    assert len(installed.json()) == 1  # left in place, not force-uninstalled

    other_token, other_org_id = await _register_and_create_org(client, {**register_payload, "email": "other-suspend@example.com"})
    blocked_new_install = await client.post(f"/organizations/{other_org_id}/plugins/{plugin_id}/install", headers=_auth_header(other_token))
    assert blocked_new_install.status_code == 400  # a suspended plugin blocks NEW installs, same as NotApprovedError


# ------------------------------------------------------------------------ Versioning

async def test_republish_creates_a_new_real_version_and_resets_to_pending(client, db_session, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    created = await client.post(
        f"/organizations/{org_id}/plugins/publish", data={"name": "Versioned Plugin", "description": "v1"},
        files=_files(_valid_manifest(name="Versioned Plugin", version="1.0.0")), headers=_auth_header(token),
    )
    plugin_id = created.json()["id"]
    await _promote_to_superadmin(db_session, register_payload["email"])
    await client.post(f"/admin/plugins/{plugin_id}/approve", headers=_auth_header(token))

    republished = await client.put(
        f"/organizations/{org_id}/plugins/{plugin_id}",
        data={"description": "v2 -- improved", "changelog": "Fixed a real bug"},
        files=_files(_valid_manifest(name="Versioned Plugin", version="1.1.0")), headers=_auth_header(token),
    )
    assert republished.status_code == 200
    assert republished.json()["version"] == "1.1.0"
    assert republished.json()["status"] == "pending"  # re-review required, real approval does not carry over

    versions = await client.get(f"/marketplace/plugins/{plugin_id}/versions")
    assert versions.status_code == 200
    assert {v["version"] for v in versions.json()} == {"1.0.0", "1.1.0"}
    changelog_entry = next(v for v in versions.json() if v["version"] == "1.1.0")
    assert changelog_entry["changelog"] == "Fixed a real bug"


async def test_republish_rejects_a_version_already_published(client, db_session, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    created = await client.post(
        f"/organizations/{org_id}/plugins/publish", data={"name": "Dup Version Plugin", "description": "..."},
        files=_files(_valid_manifest(name="Dup Version Plugin", version="1.0.0")), headers=_auth_header(token),
    )
    plugin_id = created.json()["id"]

    response = await client.put(
        f"/organizations/{org_id}/plugins/{plugin_id}", data={},
        files=_files(_valid_manifest(name="Dup Version Plugin", version="1.0.0")), headers=_auth_header(token),
    )
    assert response.status_code == 400


# ------------------------------------------------------------------------ Pricing (item 6)

async def test_publish_plugin_defaults_to_free(client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    response = await client.post(
        f"/organizations/{org_id}/plugins/publish", data={"name": "Default Pricing Plugin", "description": "..."},
        files=_files(_valid_manifest(name="Default Pricing Plugin")), headers=_auth_header(token),
    )
    assert response.status_code == 201
    assert response.json()["pricing"] == "free"
    assert response.json()["price"] is None


async def test_publish_paid_plugin_requires_a_real_price(client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    response = await client.post(
        f"/organizations/{org_id}/plugins/publish", data={"name": "Paid No Price Plugin", "description": "...", "pricing": "paid"},
        files=_files(_valid_manifest(name="Paid No Price Plugin")), headers=_auth_header(token),
    )
    assert response.status_code == 400


async def test_publish_paid_plugin_with_a_real_price(client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    response = await client.post(
        f"/organizations/{org_id}/plugins/publish", data={"name": "Paid Plugin", "description": "...", "pricing": "paid", "price": "19.99"},
        files=_files(_valid_manifest(name="Paid Plugin")), headers=_auth_header(token),
    )
    assert response.status_code == 201
    assert response.json()["pricing"] == "paid"
    assert float(response.json()["price"]) == 19.99


async def test_publish_free_plugin_rejects_a_price(client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    response = await client.post(
        f"/organizations/{org_id}/plugins/publish", data={"name": "Free With Price Plugin", "description": "...", "pricing": "free", "price": "5.00"},
        files=_files(_valid_manifest(name="Free With Price Plugin")), headers=_auth_header(token),
    )
    assert response.status_code == 400


# ------------------------------------------------------------------------ Hook permission gating (item 5)

async def test_hook_skips_plugin_missing_the_required_permission(client, db_session, register_payload):
    """api/services/plugin_hooks.py's own trigger_hook: a plugin
    subscribed to on_document_uploaded but never declaring
    read:documents is real, valid, and installed -- but is skipped for
    that hook, not executed with data it never asked to be trusted
    with."""
    token, org_id, plugin_id = await _publish_and_approve(
        client, db_session, register_payload, name="No Permission Hook Plugin",
        manifest_overrides={"entry_point": "index.py", "permissions": [], "hooks": ["on_document_uploaded"]},
    )
    await client.post(f"/organizations/{org_id}/plugins/{plugin_id}/install", headers=_auth_header(token))

    from api.services.plugin_hooks import PluginHook, trigger_hook

    executions = await trigger_hook(db_session, uuid.UUID(org_id), PluginHook.on_document_uploaded, {"document_id": "does-not-matter"})
    assert executions == []


async def test_hook_runs_plugin_that_declares_the_required_permission(client, db_session, register_payload):
    token, org_id, plugin_id = await _publish_and_approve(
        client, db_session, register_payload, name="Has Permission Hook Plugin",
        manifest_overrides={"entry_point": "index.py", "permissions": ["read:documents"], "hooks": ["on_document_uploaded"]},
        code=b"import sys, json\ndata = json.loads(sys.stdin.read())\nprint(json.dumps({\"ok\": True}))\n",
    )
    await client.post(f"/organizations/{org_id}/plugins/{plugin_id}/install", headers=_auth_header(token))

    from api.services.plugin_hooks import PluginHook, trigger_hook

    executions = await trigger_hook(db_session, uuid.UUID(org_id), PluginHook.on_document_uploaded, {"document_id": "does-not-matter"})
    assert len(executions) == 1
    assert executions[0].status.value == "success"

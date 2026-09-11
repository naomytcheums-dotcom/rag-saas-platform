"""Partie 16 (ter) -- real sandboxed plugin execution. Deliberately does
NOT mock api.security.plugin_sandbox.run_plugin_sandboxed -- these
tests spawn REAL `python`/`node` subprocesses (only S3 is mocked, same
as every other plugin test file) to actually prove the isolation
claims in plugin_sandbox.py's own docstring: a real separate process, a
real timeout, real "no ambient environment leaked in". A pure-mock test
suite would only prove the code calls subprocess.run with plausible
arguments, not that the isolation is real."""

import pytest

from plugin_test_helpers import _auth_header, _mock_s3_fixture, _publish_and_approve

_mock_s3 = pytest.fixture(autouse=True)(_mock_s3_fixture)

_ECHO_PLUGIN_CODE = b"""
import sys, json
data = json.loads(sys.stdin.read())
print(json.dumps({"received": data, "doubled": data.get("n", 0) * 2}))
"""

_ERRORING_PLUGIN_CODE = b"""
import sys
sys.exit(1)
"""

_SLOW_PLUGIN_CODE = b"""
import time
time.sleep(5)
"""

_ENV_LEAK_CHECK_CODE = b"""
import os, json
print(json.dumps({"leaked_secret_visible": "PLUGIN_SANDBOX_TEST_SECRET" in os.environ}))
"""


async def test_execute_plugin_real_success(client, db_session, register_payload):
    token, org_id, plugin_id = await _publish_and_approve(
        client, db_session, register_payload, name="Echo Plugin", manifest_overrides={"entry_point": "index.py"}, code=_ECHO_PLUGIN_CODE,
    )

    response = await client.post(f"/organizations/{org_id}/plugins/{plugin_id}/execute", json={"data": {"n": 21}}, headers=_auth_header(token))
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "success"
    assert body["output_payload"] == {"received": {"n": 21}, "doubled": 42}
    assert body["duration_ms"] is not None

    history = await client.get(f"/organizations/{org_id}/plugins/{plugin_id}/executions", headers=_auth_header(token))
    assert len(history.json()) == 1
    assert history.json()[0]["status"] == "success"


async def test_execute_plugin_real_error_is_recorded_not_raised(client, db_session, register_payload):
    token, org_id, plugin_id = await _publish_and_approve(
        client, db_session, register_payload, name="Erroring Plugin", manifest_overrides={"entry_point": "index.py"}, code=_ERRORING_PLUGIN_CODE,
    )

    response = await client.post(f"/organizations/{org_id}/plugins/{plugin_id}/execute", json={"data": {}}, headers=_auth_header(token))
    assert response.status_code == 201  # a plugin-side failure is a real, recorded execution, not an API 500
    body = response.json()
    assert body["status"] == "error"
    assert body["output_payload"] is None


async def test_execute_plugin_real_timeout(client, db_session, register_payload, monkeypatch):
    from api.config import settings

    monkeypatch.setattr(settings, "PLUGINS_MAX_EXECUTION_TIME", 1)  # real, short timeout so this test stays fast
    token, org_id, plugin_id = await _publish_and_approve(
        client, db_session, register_payload, name="Slow Plugin", manifest_overrides={"entry_point": "index.py"}, code=_SLOW_PLUGIN_CODE,
    )

    response = await client.post(f"/organizations/{org_id}/plugins/{plugin_id}/execute", json={"data": {}}, headers=_auth_header(token))
    assert response.status_code == 201
    assert response.json()["status"] == "timeout"


async def test_execute_plugin_gets_no_ambient_environment(client, db_session, register_payload, monkeypatch):
    """Real proof of plugin_sandbox.py's own "no ambient authority"
    claim: a real secret set in THIS test process's environment must
    NOT be visible inside the sandboxed subprocess."""
    monkeypatch.setenv("PLUGIN_SANDBOX_TEST_SECRET", "should-never-leak")
    token, org_id, plugin_id = await _publish_and_approve(
        client, db_session, register_payload, name="Env Check Plugin", manifest_overrides={"entry_point": "index.py"}, code=_ENV_LEAK_CHECK_CODE,
    )

    response = await client.post(f"/organizations/{org_id}/plugins/{plugin_id}/execute", json={"data": {}}, headers=_auth_header(token))
    assert response.status_code == 201
    assert response.json()["output_payload"] == {"leaked_secret_visible": False}


async def test_execute_plugin_requires_approved_status(client, register_payload):
    from plugin_test_helpers import _files, _register_and_create_org, _valid_manifest

    token, org_id = await _register_and_create_org(client, register_payload)
    created = await client.post(
        f"/organizations/{org_id}/plugins/publish", data={"name": "Unapproved Execute Plugin", "description": "..."},
        files=_files(_valid_manifest(name="Unapproved Execute Plugin")), headers=_auth_header(token),
    )
    plugin_id = created.json()["id"]

    response = await client.post(f"/organizations/{org_id}/plugins/{plugin_id}/execute", json={"data": {}}, headers=_auth_header(token))
    assert response.status_code == 400


async def test_execute_plugin_rate_limited(client, db_session, register_payload, monkeypatch):
    from api.config import settings

    monkeypatch.setattr(settings, "PLUGINS_MAX_API_CALLS", 1)
    token, org_id, plugin_id = await _publish_and_approve(
        client, db_session, register_payload, name="Rate Limited Plugin", manifest_overrides={"entry_point": "index.py"}, code=_ECHO_PLUGIN_CODE,
    )

    first = await client.post(f"/organizations/{org_id}/plugins/{plugin_id}/execute", json={"data": {"n": 1}}, headers=_auth_header(token))
    assert first.status_code == 201

    second = await client.post(f"/organizations/{org_id}/plugins/{plugin_id}/execute", json={"data": {"n": 1}}, headers=_auth_header(token))
    assert second.status_code == 429


async def test_execute_plugin_honestly_refuses_when_sandbox_disabled(client, db_session, register_payload, monkeypatch):
    from api.config import settings

    monkeypatch.setattr(settings, "PLUGINS_SANDBOX_ENABLED", False)
    token, org_id, plugin_id = await _publish_and_approve(
        client, db_session, register_payload, name="Sandbox Off Plugin", manifest_overrides={"entry_point": "index.py"}, code=_ECHO_PLUGIN_CODE,
    )

    response = await client.post(f"/organizations/{org_id}/plugins/{plugin_id}/execute", json={"data": {}}, headers=_auth_header(token))
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "error"
    assert "PLUGINS_SANDBOX_ENABLED" in body["error_message"]


async def test_execute_plugin_disabled_platform_wide(client, db_session, register_payload, monkeypatch):
    from api.config import settings

    monkeypatch.setattr(settings, "PLUGINS_ENABLED", False)
    token, org_id, plugin_id = await _publish_and_approve(
        client, db_session, register_payload, name="Platform Disabled Plugin", manifest_overrides={"entry_point": "index.py"}, code=_ECHO_PLUGIN_CODE,
    )

    response = await client.post(f"/organizations/{org_id}/plugins/{plugin_id}/execute", json={"data": {}}, headers=_auth_header(token))
    assert response.status_code == 503


async def test_execute_plugin_requires_declared_permission(client, db_session, register_payload):
    """Partie 16 (ter), extended -- api/services/plugins.py's own
    execute_plugin(required_permission=...) real gate: a plugin that
    never declared the permission is refused with a real 403; one that
    did declare it runs normally."""
    token, org_id, plugin_id = await _publish_and_approve(
        client, db_session, register_payload, name="Permission Gated Plugin",
        manifest_overrides={"entry_point": "index.py", "permissions": ["read:agents"]}, code=_ECHO_PLUGIN_CODE,
    )

    missing = await client.post(
        f"/organizations/{org_id}/plugins/{plugin_id}/execute", json={"data": {"n": 1}, "required_permission": "read:documents"}, headers=_auth_header(token),
    )
    assert missing.status_code == 403

    present = await client.post(
        f"/organizations/{org_id}/plugins/{plugin_id}/execute", json={"data": {"n": 1}, "required_permission": "read:agents"}, headers=_auth_header(token),
    )
    assert present.status_code == 201
    assert present.json()["status"] == "success"


async def test_execute_plugin_reports_which_real_engine_ran_it(client, db_session, register_payload):
    """Real, honest signal -- api/security/plugin_sandbox.py's own
    docstring on why `engine` is returned. Whichever engine this
    environment actually has (Docker if the real sandbox image is
    built, subprocess otherwise) is a valid, real outcome; this only
    asserts it's one of the two REAL engines, not a fabricated third
    value."""
    token, org_id, plugin_id = await _publish_and_approve(
        client, db_session, register_payload, name="Engine Reporting Plugin", manifest_overrides={"entry_point": "index.py"}, code=_ECHO_PLUGIN_CODE,
    )
    from api.security import plugin_sandbox

    response = await client.post(f"/organizations/{org_id}/plugins/{plugin_id}/execute", json={"data": {"n": 5}}, headers=_auth_header(token))
    assert response.status_code == 201
    expected_engine = "docker" if plugin_sandbox._docker_sandbox_available() else "subprocess"
    # engine isn't itself part of PluginExecutionResponse (it's an
    # internal run_plugin_sandboxed return key, not persisted on the
    # PluginExecution row) -- assert against the sandbox function
    # directly instead, the real, honest place that value comes from.
    direct_result = plugin_sandbox.run_plugin_sandboxed("index.py", _ECHO_PLUGIN_CODE, {"n": 5}, timeout_seconds=30, max_memory_mb=256)
    assert direct_result["engine"] == expected_engine
    assert direct_result["status"] == "success"

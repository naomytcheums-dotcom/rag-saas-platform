"""P0 audit fixes SEC-002 / RAG-025 -- MCP `stdio` transport = command execution.

Any organization owner could register `{"transport": "stdio", "command": ...}`
and `/test` ran it on the API host. `MCP_STDIO_ENABLED` (default False) now:
  * refuses to create/update a stdio server (403);
  * makes the MCP client refuse to spawn anything, even for a row already in
    the database;
  * when True, still restricts stdio servers to platform superadmins.

NOTHING is ever spawned by these tests: every process-launching primitive is
replaced by a tripwire that fails the test if it is reached."""

import uuid

import pytest
from sqlalchemy import func, select

from api.config import Settings, settings
from api.models.mcp_server import MCPServerConfig
from api.models.user import User, UserRole
from api.services.mcp import client as mcp_client
from api.services.mcp.client import MCPClientError, call_tool, discover_tools
from api.services.mcp.client import test_connection as mcp_test_connection


class _Tripwire:
    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        raise AssertionError("a subprocess spawn was attempted")


@pytest.fixture
def no_spawn(monkeypatch):
    """Every way the client (or anything it calls) could start a process."""
    tripwire = _Tripwire()
    monkeypatch.setattr(mcp_client, "stdio_client", tripwire)
    monkeypatch.setattr("subprocess.Popen", tripwire)
    monkeypatch.setattr("asyncio.create_subprocess_exec", tripwire)
    monkeypatch.setattr("asyncio.create_subprocess_shell", tripwire)
    monkeypatch.setattr("anyio.open_process", tripwire)
    monkeypatch.setattr("os.system", tripwire)
    return tripwire


def _bearer(token: str) -> dict:
    return {"Authorization": "Bearer " + token}


async def _register(client, db_session, email: str):
    payload = {"email": email, "password": "correct-horse-battery-staple", "accept_terms": True}
    token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    return token, await db_session.scalar(select(User).where(User.email == email))


async def _owner_with_org(client, db_session, email="stdio-owner@example.com"):
    token, user = await _register(client, db_session, email)
    org = (await client.post("/organizations", json={"name": "Stdio Org"}, headers=_bearer(token))).json()
    return token, user, uuid.UUID(org["id"])


def _stdio_payload(**extra) -> dict:
    return {"name": "evil", "transport": "stdio", "command": "python", "args": ["-c", "print('pwned')"], **extra}


async def _stdio_row(db_session, org_id, **extra) -> MCPServerConfig:
    row = MCPServerConfig(organization_id=org_id, name="legacy-stdio", transport="stdio", command="python", args=["-c", "x"], env={}, **extra)
    db_session.add(row)
    await db_session.commit()
    return row


async def _server_count(db_session) -> int:
    return await db_session.scalar(select(func.count()).select_from(MCPServerConfig))


def test_stdio_is_disabled_by_default():
    assert Settings.model_fields["MCP_STDIO_ENABLED"].default is False


# ------------------------------------------------------------------ creation / update (router)


async def test_owner_cannot_create_a_stdio_server_when_disabled(client, db_session, no_spawn, monkeypatch):
    monkeypatch.setattr(settings, "MCP_STDIO_ENABLED", False)
    token, _user, org_id = await _owner_with_org(client, db_session)

    response = await client.post(f"/organizations/{org_id}/mcp-servers", json=_stdio_payload(), headers=_bearer(token))

    assert response.status_code == 403
    assert "disabled" in response.json()["detail"]
    assert await _server_count(db_session) == 0
    assert no_spawn.calls == []


async def test_network_transports_are_unaffected_by_the_stdio_switch(client, db_session, no_spawn, monkeypatch):
    monkeypatch.setattr(settings, "MCP_STDIO_ENABLED", False)
    token, _user, org_id = await _owner_with_org(client, db_session)

    response = await client.post(
        f"/organizations/{org_id}/mcp-servers", json={"name": "ok", "transport": "streamable_http", "url": "https://example.com/mcp"},
        headers=_bearer(token),
    )

    assert response.status_code == 201


async def test_owner_cannot_create_a_stdio_server_even_when_enabled(client, db_session, no_spawn, monkeypatch):
    monkeypatch.setattr(settings, "MCP_STDIO_ENABLED", True)
    token, _user, org_id = await _owner_with_org(client, db_session)

    response = await client.post(f"/organizations/{org_id}/mcp-servers", json=_stdio_payload(), headers=_bearer(token))

    assert response.status_code == 403
    assert "superadmin" in response.json()["detail"]
    assert await _server_count(db_session) == 0


async def test_superadmin_can_create_and_update_a_stdio_server_when_enabled(client, db_session, no_spawn, monkeypatch):
    monkeypatch.setattr(settings, "MCP_STDIO_ENABLED", True)
    token, user, org_id = await _owner_with_org(client, db_session, "stdio-superadmin@example.com")
    user.role = UserRole.superadmin
    await db_session.commit()

    created = await client.post(f"/organizations/{org_id}/mcp-servers", json=_stdio_payload(), headers=_bearer(token))
    assert created.status_code == 201
    updated = await client.patch(
        f"/organizations/{org_id}/mcp-servers/{created.json()['id']}", json={"command": "python3"}, headers=_bearer(token),
    )

    assert updated.status_code == 200
    assert updated.json()["command"] == "python3"
    assert no_spawn.calls == []


async def test_superadmin_still_cannot_create_a_stdio_server_when_disabled(client, db_session, no_spawn, monkeypatch):
    monkeypatch.setattr(settings, "MCP_STDIO_ENABLED", False)
    token, user, org_id = await _owner_with_org(client, db_session, "stdio-superadmin2@example.com")
    user.role = UserRole.superadmin
    await db_session.commit()

    response = await client.post(f"/organizations/{org_id}/mcp-servers", json=_stdio_payload(), headers=_bearer(token))

    assert response.status_code == 403


@pytest.mark.parametrize("enabled", [False, True])
async def test_owner_cannot_modify_an_existing_stdio_row(client, db_session, no_spawn, monkeypatch, enabled):
    monkeypatch.setattr(settings, "MCP_STDIO_ENABLED", enabled)
    token, _user, org_id = await _owner_with_org(client, db_session)
    row = await _stdio_row(db_session, org_id)

    response = await client.patch(
        f"/organizations/{org_id}/mcp-servers/{row.id}", json={"command": "bash", "args": ["-c", "id"]}, headers=_bearer(token),
    )

    assert response.status_code == 403
    await db_session.refresh(row)
    assert row.command == "python"


async def test_owner_can_still_delete_a_leftover_stdio_row(client, db_session, no_spawn, monkeypatch):
    monkeypatch.setattr(settings, "MCP_STDIO_ENABLED", False)
    token, _user, org_id = await _owner_with_org(client, db_session)
    row = await _stdio_row(db_session, org_id)

    response = await client.delete(f"/organizations/{org_id}/mcp-servers/{row.id}", headers=_bearer(token))

    assert response.status_code == 204


# ------------------------------------------------------------------ launch (client + routes that reach it)


async def test_client_refuses_to_launch_an_existing_stdio_row_when_disabled(db_session, no_spawn, monkeypatch):
    monkeypatch.setattr(settings, "MCP_STDIO_ENABLED", False)
    server = MCPServerConfig(organization_id=None, name="legacy", transport="stdio", command="python", args=["-c", "x"], env={})

    with pytest.raises(MCPClientError, match="disabled"):
        await discover_tools(server)
    with pytest.raises(MCPClientError, match="disabled"):
        await call_tool(server, "add", {"a": 1, "b": 2})
    with pytest.raises(MCPClientError, match="disabled"):
        await mcp_test_connection(server)

    assert no_spawn.calls == []


async def test_routes_that_reach_the_client_return_502_and_spawn_nothing_when_disabled(client, db_session, no_spawn, monkeypatch):
    monkeypatch.setattr(settings, "MCP_STDIO_ENABLED", False)
    token, _user, org_id = await _owner_with_org(client, db_session)
    row = await _stdio_row(db_session, org_id)
    base = f"/organizations/{org_id}/mcp-servers/{row.id}"

    test_response = await client.post(base + "/test", headers=_bearer(token))
    sync_response = await client.post(base + "/sync", headers=_bearer(token))

    assert test_response.status_code == 502 and "disabled" in test_response.json()["detail"]
    assert sync_response.status_code == 502 and "disabled" in sync_response.json()["detail"]
    assert no_spawn.calls == []


async def test_when_enabled_the_client_reaches_the_launcher_with_the_configured_command(db_session, monkeypatch):
    """The gate opens only on the flag; the launcher itself is faked (no process)."""
    monkeypatch.setattr(settings, "MCP_STDIO_ENABLED", True)
    seen = []

    def fake_stdio_client(params):
        seen.append(params)
        raise RuntimeError("fake launcher: nothing is started")

    monkeypatch.setattr(mcp_client, "stdio_client", fake_stdio_client)
    server = MCPServerConfig(organization_id=None, name="trusted", transport="stdio", command="python", args=["-c", "x"], env={})

    # SEC-005: transport error text is hidden; `seen` below proves the launcher was reached.
    with pytest.raises(MCPClientError, match="failed to discover tools"):
        await discover_tools(server)

    assert len(seen) == 1 and seen[0].command == "python"

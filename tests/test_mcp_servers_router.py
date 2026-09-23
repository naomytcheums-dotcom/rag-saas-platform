"""Phase 5, Étape 9 -- router-level tests for the MCP CLIENT CRUD
surface (api/routers/mcp_servers.py). Discovery/call against a real
external server is proven separately (tests/test_mcp_client.py, tests/
mcp_test_server.py) -- here `discover_tools`/`call_tool` are
monkeypatched so these tests stay fast and don't need a real
subprocess per assertion (token-management rule)."""

import uuid
from unittest.mock import AsyncMock

from sqlalchemy import select

from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _create_org(client, access_token: str, name: str) -> dict:
    return (await client.post("/organizations", json={"name": name}, headers=_auth_header(access_token))).json()


async def _add_member(db_session, org_id, user_id, role: OrganizationRole):
    db_session.add(OrganizationMember(organization_id=org_id, user_id=user_id, role=role))
    await db_session.commit()


async def test_admin_can_create_and_list_mcp_servers(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(
        f"/organizations/{org['id']}/mcp-servers",
        json={"name": "GitHub MCP", "transport": "streamable_http", "url": "https://example.com/mcp"},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 201
    server_id = response.json()["id"]

    response = await client.get(f"/organizations/{org['id']}/mcp-servers", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert [s["id"] for s in response.json()] == [server_id]


async def test_create_mcp_server_rejects_an_invalid_transport(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(
        f"/organizations/{org['id']}/mcp-servers", json={"name": "Bad", "transport": "carrier-pigeon"}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 400


async def test_create_mcp_server_requires_url_for_streamable_http(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(
        f"/organizations/{org['id']}/mcp-servers", json={"name": "No URL", "transport": "streamable_http"}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 400


async def test_member_cannot_create_mcp_server(client, db_session, register_payload):
    """Validation criterion: sécurité -- les permissions sont respectées."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    member_token, member = await _register(client, db_session, "member@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member)

    response = await client.post(
        f"/organizations/{org['id']}/mcp-servers", json={"name": "X", "transport": "streamable_http", "url": "https://x.example.com"},
        headers=_auth_header(member_token),
    )
    assert response.status_code == 403


async def test_member_can_list_mcp_servers(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    member_token, member = await _register(client, db_session, "member@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member)

    response = await client.get(f"/organizations/{org['id']}/mcp-servers", headers=_auth_header(member_token))
    assert response.status_code == 200


async def test_admin_can_delete_mcp_server(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(
        f"/organizations/{org['id']}/mcp-servers", json={"name": "X", "transport": "streamable_http", "url": "https://x.example.com"},
        headers=_auth_header(owner_token),
    )
    server_id = created.json()["id"]

    response = await client.delete(f"/organizations/{org['id']}/mcp-servers/{server_id}", headers=_auth_header(owner_token))
    assert response.status_code == 204

    response = await client.get(f"/organizations/{org['id']}/mcp-servers", headers=_auth_header(owner_token))
    assert response.json() == []


async def test_a_server_from_a_different_org_returns_404(client, db_session, register_payload):
    """Validation criterion: isolation multi-tenant -- pas de fuite cross-tenant."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_a = await _create_org(client, owner_token, "Org A")
    org_b = await _create_org(client, owner_token, "Org B")
    created = await client.post(
        f"/organizations/{org_a['id']}/mcp-servers", json={"name": "X", "transport": "streamable_http", "url": "https://x.example.com"},
        headers=_auth_header(owner_token),
    )
    server_id = created.json()["id"]

    response = await client.get(f"/organizations/{org_b['id']}/mcp-servers/{server_id}/tools", headers=_auth_header(owner_token))
    assert response.status_code == 404


async def test_sync_tools_persists_a_real_discovery_result(client, db_session, register_payload, monkeypatch):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(
        f"/organizations/{org['id']}/mcp-servers", json={"name": "X", "transport": "streamable_http", "url": "https://x.example.com"},
        headers=_auth_header(owner_token),
    )
    server_id = created.json()["id"]

    monkeypatch.setattr(
        "api.services.mcp.discovery.discover_tools",
        AsyncMock(return_value=[{"name": "add", "description": "adds", "input_schema": {"properties": {"a": {"type": "integer"}}}}]),
    )

    response = await client.post(f"/organizations/{org['id']}/mcp-servers/{server_id}/sync", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert [t["name"] for t in response.json()] == ["add"]

    response = await client.get(f"/organizations/{org['id']}/mcp-servers/{server_id}/tools", headers=_auth_header(owner_token))
    assert [t["name"] for t in response.json()] == ["add"]


async def test_sync_tools_surfaces_a_real_discovery_failure_as_502(client, db_session, register_payload, monkeypatch):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(
        f"/organizations/{org['id']}/mcp-servers", json={"name": "X", "transport": "streamable_http", "url": "https://x.example.com"},
        headers=_auth_header(owner_token),
    )
    server_id = created.json()["id"]

    from api.services.mcp.client import MCPClientError

    monkeypatch.setattr("api.services.mcp.discovery.discover_tools", AsyncMock(side_effect=MCPClientError("boom")))

    response = await client.post(f"/organizations/{org['id']}/mcp-servers/{server_id}/sync", headers=_auth_header(owner_token))
    assert response.status_code == 502


async def test_call_mcp_tool_returns_a_real_result(client, db_session, register_payload, monkeypatch):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(
        f"/organizations/{org['id']}/mcp-servers", json={"name": "X", "transport": "streamable_http", "url": "https://x.example.com"},
        headers=_auth_header(owner_token),
    )
    server_id = created.json()["id"]

    monkeypatch.setattr("api.routers.mcp_servers.call_cached_tool", AsyncMock(return_value="5"))

    response = await client.post(
        f"/organizations/{org['id']}/mcp-servers/{server_id}/tools/add/call", json={"arguments": {"a": 2, "b": 3}},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    assert response.json() == {"result": "5"}

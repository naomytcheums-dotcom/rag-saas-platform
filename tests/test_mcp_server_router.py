"""Phase 5, Étape 9 -- tests for this platform's own MCP SERVER role
(api/routers/mcp_server.py): exposes the real, static tool registry
over a real, wire-compatible `tools/list`/`tools/call` HTTP surface,
gated by the org-scoped `X-API-Key` mechanism (mcp:tools scope)."""

import uuid

from sqlalchemy import select

from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.services.organization_api_keys import generate_organization_api_key


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _create_org(client, access_token: str, name: str) -> dict:
    return (await client.post("/organizations", json={"name": name}, headers=_auth_header(access_token))).json()


async def test_list_tools_requires_a_valid_api_key(client):
    response = await client.get("/mcp/v1/tools", headers={"X-API-Key": "sk_bogus"})
    assert response.status_code == 401


async def test_list_tools_requires_the_mcp_scope(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    _row, plaintext = await generate_organization_api_key(db_session, uuid.UUID(org["id"]), "no-mcp-scope", ["chat:write"])
    await db_session.commit()

    response = await client.get("/mcp/v1/tools", headers={"X-API-Key": plaintext})
    assert response.status_code == 403


async def test_list_tools_returns_the_real_registry(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    _row, plaintext = await generate_organization_api_key(db_session, uuid.UUID(org["id"]), "mcp-key", ["mcp:tools"])
    await db_session.commit()

    response = await client.get("/mcp/v1/tools", headers={"X-API-Key": plaintext})
    assert response.status_code == 200
    names = {t["name"] for t in response.json()["tools"]}
    assert "calculator" in names


async def test_call_tool_executes_a_real_registered_tool(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    _row, plaintext = await generate_organization_api_key(db_session, uuid.UUID(org["id"]), "mcp-key", ["mcp:tools"])
    await db_session.commit()

    response = await client.post(
        "/mcp/v1/tools/calculator/call", json={"arguments": {"expression": "2 + 2"}}, headers={"X-API-Key": plaintext},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_error"] is False
    assert body["content"][0]["text"] == "4"


async def test_call_tool_returns_404_for_an_unknown_tool(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    _row, plaintext = await generate_organization_api_key(db_session, uuid.UUID(org["id"]), "mcp-key", ["mcp:tools"])
    await db_session.commit()

    response = await client.post("/mcp/v1/tools/does_not_exist/call", json={"arguments": {}}, headers={"X-API-Key": plaintext})
    assert response.status_code == 404


async def test_call_tool_returns_a_real_error_result_for_invalid_arguments(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    _row, plaintext = await generate_organization_api_key(db_session, uuid.UUID(org["id"]), "mcp-key", ["mcp:tools"])
    await db_session.commit()

    response = await client.post("/mcp/v1/tools/calculator/call", json={"arguments": {}}, headers={"X-API-Key": plaintext})
    assert response.status_code == 200
    assert response.json()["is_error"] is True

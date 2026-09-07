"""Partie 5.3.5 -- tool selection. Fast SQLite suite."""

import uuid

import pytest
from sqlalchemy import select

from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.security.agents import create_agent, update_agent
from api.services.agent_tools import (
    AGENT_TOOL_CATALOG, AgentToolError, disable_tool, enable_tool, get_agent_tools, get_available_tools,
    set_agent_tools, validate_tool_config, validate_tools_list,
)


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _create_org(client, access_token: str, name: str) -> dict:
    return (await client.post("/organizations", json={"name": name}, headers=_auth_header(access_token))).json()


async def _add_member(db_session, org_id, user_id, role: OrganizationRole, invited_by=None):
    db_session.add(OrganizationMember(organization_id=org_id, user_id=user_id, role=role, invited_by=invited_by))
    await db_session.commit()


# --------------------------------------- validate_tool_config / get_available_tools --


def test_get_available_tools_lists_all_12_real_named_tools():
    """Validation criterion: le catalogue liste les 12 outils réels."""
    tools = get_available_tools()
    assert tools == AGENT_TOOL_CATALOG
    assert len(tools) == 12
    assert "search_knowledge_base" in tools and "escalate_to_human" in tools


def test_validate_tool_config_accepts_a_real_known_tool():
    validate_tool_config("web_search")  # does not raise
    validate_tool_config("calculate", {"precision": 4})


def test_validate_tool_config_rejects_an_unknown_tool():
    """Validation criterion: robustesse -- outil inconnu rejeté."""
    with pytest.raises(AgentToolError, match="Unknown tool"):
        validate_tool_config("not-a-real-tool")


def test_validate_tool_config_rejects_a_non_dict_config():
    with pytest.raises(AgentToolError, match="must be a real JSON object"):
        validate_tool_config("web_search", "not-a-dict")


def test_validate_tools_list_rejects_an_entry_missing_a_name():
    with pytest.raises(AgentToolError, match="must include a real 'name'"):
        validate_tools_list([{"enabled": True}])


# --------------------------------------- get/set/enable/disable --


async def test_get_agent_tools_returns_empty_list_when_unconfigured(db_session):
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()
    assert await get_agent_tools(db_session, agent.id) == []


async def test_set_agent_tools_persists_a_real_valid_list(db_session):
    """Validation criterion: cohérence -- les outils sélectionnés sont appliqués."""
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()

    await set_agent_tools(db_session, agent.id, [{"name": "web_search"}, {"name": "calculate", "enabled": False}])
    await db_session.commit()

    tools = await get_agent_tools(db_session, agent.id)
    assert {t["name"]: t["enabled"] for t in tools} == {"web_search": True, "calculate": False}


async def test_set_agent_tools_rejects_an_unknown_tool_name(db_session):
    """Validation criterion: sécurité/robustesse -- rejet upfront, rien n'est écrit."""
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()

    with pytest.raises(AgentToolError):
        await set_agent_tools(db_session, agent.id, [{"name": "web_search"}, {"name": "not-a-real-tool"}])

    assert await get_agent_tools(db_session, agent.id) == []


async def test_enable_tool_adds_a_new_real_tool(db_session):
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()

    await enable_tool(db_session, agent.id, "read_url")
    await db_session.commit()

    tools = await get_agent_tools(db_session, agent.id)
    assert tools == [{"name": "read_url", "enabled": True, "config": {}}]


async def test_enable_tool_re_enables_and_merges_config(db_session):
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()
    await set_agent_tools(db_session, agent.id, [{"name": "email_read", "enabled": False, "config": {"folder": "inbox"}}])
    await db_session.commit()

    await enable_tool(db_session, agent.id, "email_read", config={"limit": 5})
    await db_session.commit()

    tools = await get_agent_tools(db_session, agent.id)
    assert tools == [{"name": "email_read", "enabled": True, "config": {"folder": "inbox", "limit": 5}}]


async def test_enable_tool_rejects_an_unknown_tool(db_session):
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()
    with pytest.raises(AgentToolError):
        await enable_tool(db_session, agent.id, "not-a-real-tool")


async def test_disable_tool_keeps_config_real_soft_disable(db_session):
    """Validation criterion: robustesse -- désactiver conserve la config."""
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()
    await set_agent_tools(db_session, agent.id, [{"name": "github_get_repo", "config": {"owner": "acme"}}])
    await db_session.commit()

    await disable_tool(db_session, agent.id, "github_get_repo")
    await db_session.commit()

    tools = await get_agent_tools(db_session, agent.id)
    assert tools == [{"name": "github_get_repo", "enabled": False, "config": {"owner": "acme"}}]


async def test_disable_tool_on_a_tool_the_agent_never_had_is_a_real_no_op(db_session):
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()
    await disable_tool(db_session, agent.id, "web_search")
    await db_session.commit()
    assert await get_agent_tools(db_session, agent.id) == []


async def test_update_agent_rejects_an_unknown_tool_name_via_generic_update(db_session):
    """Validation criterion: sécurité -- pas de contournement via l'endpoint générique."""
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()
    with pytest.raises(AgentToolError):
        await update_agent(db_session, agent.id, {"tools": [{"name": "not-a-real-tool"}]})


# --------------------------------------- endpoints --


async def test_manager_can_set_agent_tools(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]

    response = await client.patch(
        f"/agents/{agent_id}/tools", json={"tools": [{"name": "web_search"}]}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    assert response.json()["tools"] == [{"name": "web_search", "enabled": True, "config": {}}]


async def test_member_cannot_set_agent_tools(client, db_session, register_payload):
    """Validation criterion: sécurité -- les permissions sont respectées."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]
    member_token, member = await _register(client, db_session, "member@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member)

    response = await client.patch(
        f"/agents/{agent_id}/tools", json={"tools": [{"name": "web_search"}]}, headers=_auth_header(member_token),
    )
    assert response.status_code == 403


async def test_set_agent_tools_endpoint_rejects_an_unknown_tool(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]

    response = await client.patch(
        f"/agents/{agent_id}/tools", json={"tools": [{"name": "not-a-real-tool"}]}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 400


async def test_enable_and_disable_agent_tool_endpoints(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]

    enable_response = await client.post(f"/agents/{agent_id}/tools/calculate/enable", json={}, headers=_auth_header(owner_token))
    assert enable_response.status_code == 200
    assert enable_response.json()["tools"] == [{"name": "calculate", "enabled": True, "config": {}}]

    disable_response = await client.post(f"/agents/{agent_id}/tools/calculate/disable", headers=_auth_header(owner_token))
    assert disable_response.status_code == 200
    assert disable_response.json()["tools"] == [{"name": "calculate", "enabled": False, "config": {}}]


async def test_get_agent_tools_endpoint(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]

    response = await client.get(f"/agents/{agent_id}/tools", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["tools"] == []


async def test_list_available_tools_endpoint(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    response = await client.get("/tools/available", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert len(response.json()) == 12


async def test_create_agent_rejects_an_unknown_tool_name(client, db_session, register_payload):
    """Validation criterion: sécurité -- create_agent lui-même est protégé."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(
        f"/organizations/{org['id']}/agents",
        json={"name": "Bot", "tools": [{"name": "not-a-real-tool"}]},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 400

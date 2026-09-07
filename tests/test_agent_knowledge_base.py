"""Partie 5.3.4 -- knowledge base selection. Fast SQLite suite."""

import uuid

import pytest
from sqlalchemy import select

from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.models.workspace import Workspace
from api.security.agents import create_agent
from api.services.agent_knowledge_base import (
    AgentKnowledgeBaseError, get_agent_kb_config, get_agent_knowledge_base, get_available_knowledge_bases,
    set_agent_knowledge_base, validate_knowledge_base_access,
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


async def _make_workspace(db_session, organization_id, name="KB") -> Workspace:
    workspace = Workspace(organization_id=organization_id, name=name)
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    return workspace


# --------------------------------------- validate_knowledge_base_access --


async def test_validate_knowledge_base_access_accepts_a_real_workspace_in_the_same_org(db_session):
    """Validation criterion: la validation fonctionne."""
    org_id = uuid.uuid4()
    workspace = await _make_workspace(db_session, org_id)
    result = await validate_knowledge_base_access(db_session, org_id, workspace.id)
    assert result.id == workspace.id


async def test_validate_knowledge_base_access_rejects_a_workspace_from_another_org(db_session):
    """Validation criterion: sécurité -- pas de fuite inter-organisation."""
    workspace = await _make_workspace(db_session, uuid.uuid4())
    with pytest.raises(AgentKnowledgeBaseError, match="was not found"):
        await validate_knowledge_base_access(db_session, uuid.uuid4(), workspace.id)


async def test_validate_knowledge_base_access_rejects_an_unknown_workspace(db_session):
    with pytest.raises(AgentKnowledgeBaseError):
        await validate_knowledge_base_access(db_session, uuid.uuid4(), uuid.uuid4())


# --------------------------------------- get/set_agent_knowledge_base --


async def test_get_agent_knowledge_base_returns_none_when_unconfigured(db_session):
    org_id = uuid.uuid4()
    agent = await create_agent(db_session, org_id, {"name": "Bot"}, None)
    await db_session.commit()
    assert await get_agent_knowledge_base(db_session, agent.id) is None


async def test_set_agent_knowledge_base_persists_a_real_valid_workspace(db_session):
    """Validation criterion: cohérence -- la KB sélectionnée est appliquée."""
    org_id = uuid.uuid4()
    agent = await create_agent(db_session, org_id, {"name": "Bot"}, None)
    await db_session.commit()
    workspace = await _make_workspace(db_session, org_id)

    await set_agent_knowledge_base(db_session, agent.id, workspace.id)
    await db_session.commit()

    assert await get_agent_knowledge_base(db_session, agent.id) == workspace.id


async def test_set_agent_knowledge_base_rejects_a_workspace_from_another_org(db_session):
    """Validation criterion: sécurité -- rejet inter-organisation."""
    org_id = uuid.uuid4()
    agent = await create_agent(db_session, org_id, {"name": "Bot"}, None)
    await db_session.commit()
    other_workspace = await _make_workspace(db_session, uuid.uuid4())

    with pytest.raises(AgentKnowledgeBaseError):
        await set_agent_knowledge_base(db_session, agent.id, other_workspace.id)


async def test_set_agent_knowledge_base_can_unset_with_none(db_session):
    org_id = uuid.uuid4()
    agent = await create_agent(db_session, org_id, {"name": "Bot"}, None)
    await db_session.commit()
    workspace = await _make_workspace(db_session, org_id)
    await set_agent_knowledge_base(db_session, agent.id, workspace.id)
    await db_session.commit()

    await set_agent_knowledge_base(db_session, agent.id, None)
    await db_session.commit()

    assert await get_agent_knowledge_base(db_session, agent.id) is None


async def test_set_agent_knowledge_base_merges_config_over_defaults(db_session):
    org_id = uuid.uuid4()
    agent = await create_agent(db_session, org_id, {"name": "Bot"}, None)
    await db_session.commit()
    workspace = await _make_workspace(db_session, org_id)

    await set_agent_knowledge_base(db_session, agent.id, workspace.id, config={"top_k": 15})
    await db_session.commit()

    config = await get_agent_kb_config(db_session, agent.id)
    assert config["top_k"] == 15
    assert "score_threshold" in config


# --------------------------------------- get_agent_kb_config / get_available_knowledge_bases --


async def test_get_agent_kb_config_returns_real_defaults_when_unconfigured(db_session):
    """Validation criterion: la configuration de la KB est correcte."""
    org_id = uuid.uuid4()
    agent = await create_agent(db_session, org_id, {"name": "Bot"}, None)
    await db_session.commit()

    config = await get_agent_kb_config(db_session, agent.id)
    assert "top_k" in config and "score_threshold" in config


async def test_get_available_knowledge_bases_lists_workspaces_in_the_org(db_session):
    """Validation criterion: les KB disponibles sont listées."""
    org_id = uuid.uuid4()
    workspace_a = await _make_workspace(db_session, org_id, "A")
    workspace_b = await _make_workspace(db_session, org_id, "B")
    await _make_workspace(db_session, uuid.uuid4(), "Other org")

    result = await get_available_knowledge_bases(db_session, org_id)
    ids = {w.id for w in result}
    assert ids == {workspace_a.id, workspace_b.id}


# --------------------------------------- endpoints --


async def test_manager_can_set_agent_knowledge_base(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]
    workspace = await _make_workspace(db_session, uuid.UUID(org["id"]))

    response = await client.patch(
        f"/agents/{agent_id}/knowledge-base", json={"knowledge_base_id": str(workspace.id)}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    assert response.json()["knowledge_base_id"] == str(workspace.id)


async def test_member_cannot_set_agent_knowledge_base(client, db_session, register_payload):
    """Validation criterion: sécurité -- les permissions sont respectées."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]
    member_token, member = await _register(client, db_session, "member@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member)
    workspace = await _make_workspace(db_session, uuid.UUID(org["id"]))

    response = await client.patch(
        f"/agents/{agent_id}/knowledge-base", json={"knowledge_base_id": str(workspace.id)}, headers=_auth_header(member_token),
    )
    assert response.status_code == 403


async def test_set_agent_knowledge_base_endpoint_rejects_cross_org_workspace(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]
    other_workspace = await _make_workspace(db_session, uuid.uuid4())

    response = await client.patch(
        f"/agents/{agent_id}/knowledge-base", json={"knowledge_base_id": str(other_workspace.id)}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 400


async def test_update_agent_knowledge_base_config_only_does_not_clear_the_kb(client, db_session, register_payload):
    """A PATCH carrying only `config` must not clear an already-set KB."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]
    workspace = await _make_workspace(db_session, uuid.UUID(org["id"]))
    await client.patch(f"/agents/{agent_id}/knowledge-base", json={"knowledge_base_id": str(workspace.id)}, headers=_auth_header(owner_token))

    response = await client.patch(f"/agents/{agent_id}/knowledge-base", json={"config": {"top_k": 20}}, headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["knowledge_base_id"] == str(workspace.id)
    assert response.json()["config"]["top_k"] == 20


async def test_get_agent_knowledge_base_endpoint(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]

    response = await client.get(f"/agents/{agent_id}/knowledge-base", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["knowledge_base_id"] is None


async def test_get_agent_kb_config_endpoint(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]

    response = await client.get(f"/agents/{agent_id}/knowledge-base/config", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert "top_k" in response.json()


async def test_list_agent_knowledge_base_options_endpoint(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]
    await _make_workspace(db_session, uuid.UUID(org["id"]), "Docs")

    response = await client.get(f"/agents/{agent_id}/knowledge-base/options", headers=_auth_header(owner_token))
    assert response.status_code == 200
    names = [w["name"] for w in response.json()]
    assert "Docs" in names


async def test_create_agent_rejects_a_cross_org_knowledge_base_id(client, db_session, register_payload):
    """Validation criterion: sécurité -- create_agent lui-même est protégé."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    other_workspace = await _make_workspace(db_session, uuid.uuid4())

    response = await client.post(
        f"/organizations/{org['id']}/agents",
        json={"name": "Bot", "knowledge_base_id": str(other_workspace.id)},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 400

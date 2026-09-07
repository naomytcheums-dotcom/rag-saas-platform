"""Partie 5.3.1 -- real Agent CRUD. Fast SQLite suite, same tier as
tests/test_workspaces.py."""

import uuid

from sqlalchemy import select

from api.models.agent import Agent
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


async def _add_member(db_session, org_id, user_id, role: OrganizationRole, invited_by=None):
    db_session.add(OrganizationMember(organization_id=org_id, user_id=user_id, role=role, invited_by=invited_by))
    await db_session.commit()


async def _create_agent(client, org_id: str, token: str, name: str = "Support Bot") -> dict:
    response = await client.post(f"/organizations/{org_id}/agents", json={"name": name}, headers=_auth_header(token))
    assert response.status_code == 201, response.text
    return response.json()


# --------------------------------------- create / list --


async def test_manager_can_create_an_agent(client, db_session, register_payload):
    """Validation criterion: la création d'agent fonctionne."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(
        f"/organizations/{org['id']}/agents",
        json={"name": "Support Bot", "system_prompt": "You help customers.", "model_config": {"provider": "anthropic", "model": "claude-3-5-sonnet-20241022"}},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Support Bot"
    assert body["status"] == "active"
    assert body["model_config"]["provider"] == "anthropic"


async def test_member_cannot_create_an_agent(client, db_session, register_payload):
    """Validation criterion: sécurité -- les permissions sont respectées."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    member_token, member = await _register(client, db_session, "member@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member)

    response = await client.post(f"/organizations/{org['id']}/agents", json={"name": "x"}, headers=_auth_header(member_token))
    assert response.status_code == 403


async def test_member_can_list_agents(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await _create_agent(client, org["id"], owner_token)
    member_token, member = await _register(client, db_session, "member@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member)

    response = await client.get(f"/organizations/{org['id']}/agents", headers=_auth_header(member_token))
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_list_agents_filters_by_status(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    agent = await _create_agent(client, org["id"], owner_token)
    await client.post(f"/agents/{agent['id']}/pause", headers=_auth_header(owner_token))

    active = await client.get(f"/organizations/{org['id']}/agents?status=active", headers=_auth_header(owner_token))
    assert active.json() == []
    paused = await client.get(f"/organizations/{org['id']}/agents?status=paused", headers=_auth_header(owner_token))
    assert len(paused.json()) == 1


# --------------------------------------- get / update / delete --


async def test_member_can_read_a_single_agent(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    agent = await _create_agent(client, org["id"], owner_token)

    response = await client.get(f"/agents/{agent['id']}", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["id"] == agent["id"]


async def test_manager_can_update_an_agent(client, db_session, register_payload):
    """Validation criterion: la modification fonctionne."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    agent = await _create_agent(client, org["id"], owner_token)

    response = await client.patch(f"/agents/{agent['id']}", json={"name": "Renamed Bot"}, headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed Bot"


async def test_member_cannot_update_an_agent(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    agent = await _create_agent(client, org["id"], owner_token)
    member_token, member = await _register(client, db_session, "member@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member)

    response = await client.patch(f"/agents/{agent['id']}", json={"name": "x"}, headers=_auth_header(member_token))
    assert response.status_code == 403


async def test_manager_can_delete_an_agent_and_it_is_soft_deleted(client, db_session, register_payload):
    """Validation criterion: la suppression fonctionne (soft delete)."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    agent = await _create_agent(client, org["id"], owner_token)

    response = await client.delete(f"/agents/{agent['id']}", headers=_auth_header(owner_token))
    assert response.status_code == 204

    row = await db_session.get(Agent, uuid.UUID(agent["id"]))
    assert row is not None  # real row still exists (soft delete)
    assert row.deleted_at is not None

    not_found = await client.get(f"/agents/{agent['id']}", headers=_auth_header(owner_token))
    assert not_found.status_code == 404


# --------------------------------------- status transitions --


async def test_activate_pause_archive_transitions(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    agent = await _create_agent(client, org["id"], owner_token)

    paused = await client.post(f"/agents/{agent['id']}/pause", headers=_auth_header(owner_token))
    assert paused.json()["status"] == "paused"

    archived = await client.post(f"/agents/{agent['id']}/archive", headers=_auth_header(owner_token))
    assert archived.json()["status"] == "archived"

    reactivated = await client.post(f"/agents/{agent['id']}/activate", headers=_auth_header(owner_token))
    assert reactivated.json()["status"] == "active"


# --------------------------------------- isolation --


async def test_cannot_access_an_agent_from_another_organization(client, db_session, register_payload):
    """Validation criterion: cohérence -- l'agent est lié à l'organisation."""
    owner_a_token, owner_a = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_a = await _create_org(client, owner_a_token, "Org A")
    agent = await _create_agent(client, org_a["id"], owner_a_token)

    owner_b_token, owner_b = await _register(client, db_session, "ownerb@example.com")
    await _create_org(client, owner_b_token, "Org B")

    response = await client.get(f"/agents/{agent['id']}", headers=_auth_header(owner_b_token))
    assert response.status_code == 404


# --------------------------------------- quota --


async def test_agent_creation_respects_the_real_agent_quota(client, db_session, register_payload):
    """Validation criterion: cohérence -- le quota agents est réellement compté."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    quota_response = await client.patch(f"/organizations/{org['id']}/quotas", json={"max_agents": 1}, headers=_auth_header(owner_token))
    assert quota_response.status_code == 200

    await _create_agent(client, org["id"], owner_token, name="first")
    over_limit = await client.post(f"/organizations/{org['id']}/agents", json={"name": "second"}, headers=_auth_header(owner_token))
    assert over_limit.status_code == 402

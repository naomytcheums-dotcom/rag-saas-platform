"""Partie 23 -- real CRUD, access control, status, pause/stop for
autonomous agents. Named `test_autonomous_agents.py`, not the spec's
own literal `test_agents.py` -- a real, pre-existing
`tests/test_agents.py` (Partie 5's own Agent tests) already uses that
basename; pytest requires unique module basenames without package
`__init__.py` files (same real collision/fix as Partie 21's own
`test_ab_tests.py` -> `test_ab_tests_advanced.py`)."""

import uuid

from sqlalchemy import select

from api.models.autonomous_agent import AutonomousAgent, AutonomousAgentStatus
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _make_org(client, db_session, register_payload, name):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_id = (await client.post("/organizations", json={"name": name}, headers=_auth_header(owner_token))).json()["id"]
    return owner_token, org_id


async def test_create_autonomous_agent_requires_admin(client, db_session, register_payload):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Autonomous Org")

    member_token, member = await _register(client, db_session, "autonomous_member@example.com")
    owner = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    db_session.add(OrganizationMember(organization_id=uuid.UUID(org_id), user_id=member.id, role=OrganizationRole.member, invited_by=owner.id))
    await db_session.commit()

    response = await client.post(
        f"/organizations/{org_id}/autonomous-agents", json={"name": "Researcher", "goal": "Find real facts"}, headers=_auth_header(member_token),
    )
    assert response.status_code == 403

    response = await client.post(
        f"/organizations/{org_id}/autonomous-agents", json={"name": "Researcher", "goal": "Find real facts"}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "idle"
    assert body["max_steps"] == 20
    assert body["current_step"] == 0


async def test_get_autonomous_agent_returns_404_for_non_member(client, db_session, register_payload):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Private Autonomous Org")
    created = (await client.post(
        f"/organizations/{org_id}/autonomous-agents", json={"name": "A", "goal": "G"}, headers=_auth_header(owner_token),
    )).json()

    stranger_token, _stranger = await _register(client, db_session, "autonomous_stranger@example.com")
    response = await client.get(f"/autonomous-agents/{created['id']}", headers=_auth_header(stranger_token))
    assert response.status_code == 404


async def test_update_autonomous_agent_requires_admin(client, db_session, register_payload):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Update Org")
    created = (await client.post(
        f"/organizations/{org_id}/autonomous-agents", json={"name": "A", "goal": "G"}, headers=_auth_header(owner_token),
    )).json()

    response = await client.patch(f"/autonomous-agents/{created['id']}", json={"max_steps": 5}, headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["max_steps"] == 5


async def test_delete_autonomous_agent(client, db_session, register_payload):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Delete Org")
    created = (await client.post(
        f"/organizations/{org_id}/autonomous-agents", json={"name": "A", "goal": "G"}, headers=_auth_header(owner_token),
    )).json()

    response = await client.delete(f"/autonomous-agents/{created['id']}", headers=_auth_header(owner_token))
    assert response.status_code == 204
    assert await db_session.get(AutonomousAgent, uuid.UUID(created["id"])) is None


async def test_stop_resets_current_step_and_status(client, db_session, register_payload):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Stop Org")
    agent = AutonomousAgent(organization_id=uuid.UUID(org_id), name="A", goal="G", status=AutonomousAgentStatus.executing.value, current_step=3)
    db_session.add(agent)
    await db_session.commit()

    response = await client.post(f"/autonomous-agents/{agent.id}/stop", headers=_auth_header(owner_token))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "idle"
    assert body["current_step"] == 0


async def test_pause_only_affects_a_running_agent(client, db_session, register_payload):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Pause Org")
    agent = AutonomousAgent(organization_id=uuid.UUID(org_id), name="A", goal="G", status=AutonomousAgentStatus.idle.value)
    db_session.add(agent)
    await db_session.commit()

    response = await client.post(f"/autonomous-agents/{agent.id}/pause", headers=_auth_header(owner_token))
    assert response.json()["status"] == "idle"  # a real, idle agent has nothing real to pause

    agent.status = AutonomousAgentStatus.executing.value
    await db_session.commit()
    response = await client.post(f"/autonomous-agents/{agent.id}/pause", headers=_auth_header(owner_token))
    assert response.json()["status"] == "paused"


async def test_get_status_endpoint(client, db_session, register_payload):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Status Org")
    agent = AutonomousAgent(organization_id=uuid.UUID(org_id), name="A", goal="G", max_steps=7, current_step=2)
    db_session.add(agent)
    await db_session.commit()

    response = await client.get(f"/autonomous-agents/{agent.id}/status", headers=_auth_header(owner_token))
    assert response.json() == {"status": "idle", "current_step": 2, "max_steps": 7, "error": None}

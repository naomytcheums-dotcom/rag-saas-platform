"""Phase 5, Étape 6 -- long-term (cross-run) agent memory. Fast SQLite
suite for the service layer, real client+db_session suite for the
endpoints (same convention as tests/test_agent_memory_config.py)."""

import datetime as dt
import uuid

from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from sqlalchemy import select

from api.security.agents import create_agent
from api.services.agent_long_term_memory import delete_long_term_memory, get_long_term_memory, set_long_term_memory


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


# ------------------------------------------------------- service layer --


async def test_set_and_get_long_term_memory_org_wide(db_session):
    """Validation criterion: écriture/lecture d'un fait cross-run, sans utilisateur."""
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await set_long_term_memory(db_session, agent.id, "escalation_email", "ops@example.com")
    await db_session.commit()

    memory = await get_long_term_memory(db_session, agent.id)
    assert memory == {"escalation_email": "ops@example.com"}


async def test_set_long_term_memory_upserts_an_existing_key(db_session):
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await set_long_term_memory(db_session, agent.id, "step", 1)
    await set_long_term_memory(db_session, agent.id, "step", 2)
    await db_session.commit()

    assert await get_long_term_memory(db_session, agent.id) == {"step": 2}


async def test_per_user_value_overrides_org_wide_value_on_key_collision(db_session):
    """Validation criterion: un fait plus spécifique (utilisateur) l'emporte sur un fait général."""
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    user_id = uuid.uuid4()
    await set_long_term_memory(db_session, agent.id, "units", "metric")
    await set_long_term_memory(db_session, agent.id, "units", "imperial", user_id=user_id)
    await db_session.commit()

    assert await get_long_term_memory(db_session, agent.id, user_id=user_id) == {"units": "imperial"}
    assert await get_long_term_memory(db_session, agent.id) == {"units": "metric"}


async def test_user_specific_memory_is_not_visible_to_a_different_user(db_session):
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await set_long_term_memory(db_session, agent.id, "pref", "dark_mode", user_id=uuid.uuid4())
    await db_session.commit()

    assert await get_long_term_memory(db_session, agent.id, user_id=uuid.uuid4()) == {}


async def test_expired_long_term_memory_is_lazily_deleted_and_excluded(db_session):
    """Validation criterion: l'expiration est réelle, pas seulement documentée."""
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    past = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)
    await set_long_term_memory(db_session, agent.id, "temp_fact", "gone", expires_at=past)
    await db_session.commit()

    assert await get_long_term_memory(db_session, agent.id) == {}


async def test_long_term_memory_never_expires_by_default(db_session):
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await set_long_term_memory(db_session, agent.id, "durable_fact", "stays")
    await db_session.commit()

    assert await get_long_term_memory(db_session, agent.id) == {"durable_fact": "stays"}


async def test_delete_long_term_memory_removes_a_real_key(db_session):
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await set_long_term_memory(db_session, agent.id, "a", 1)
    await db_session.commit()

    deleted = await delete_long_term_memory(db_session, agent.id, "a")
    await db_session.commit()

    assert deleted is True
    assert await get_long_term_memory(db_session, agent.id) == {}


async def test_delete_long_term_memory_returns_false_honestly_for_a_missing_key(db_session):
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    assert await delete_long_term_memory(db_session, agent.id, "never-set") is False


async def test_delete_long_term_memory_does_not_touch_another_agents_memory(db_session):
    agent_a = await create_agent(db_session, uuid.uuid4(), {"name": "A"}, None)
    agent_b = await create_agent(db_session, uuid.uuid4(), {"name": "B"}, None)
    await set_long_term_memory(db_session, agent_a.id, "shared_key", "a-value")
    await set_long_term_memory(db_session, agent_b.id, "shared_key", "b-value")
    await db_session.commit()

    await delete_long_term_memory(db_session, agent_a.id, "shared_key")
    await db_session.commit()

    assert await get_long_term_memory(db_session, agent_a.id) == {}
    assert await get_long_term_memory(db_session, agent_b.id) == {"shared_key": "b-value"}


# ---------------------------------------------------------- endpoints --


async def test_manager_can_set_and_get_agent_long_term_memory(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]

    response = await client.put(
        f"/agents/{agent_id}/memory/escalation_email", json={"value": "ops@example.com"}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    assert response.json()["memory"] == {"escalation_email": "ops@example.com"}

    response = await client.get(f"/agents/{agent_id}/memory", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["memory"] == {"escalation_email": "ops@example.com"}


async def test_member_cannot_set_agent_long_term_memory(client, db_session, register_payload):
    """Validation criterion: sécurité -- les permissions sont respectées."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]
    member_token, member = await _register(client, db_session, "member@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member)

    response = await client.put(
        f"/agents/{agent_id}/memory/k", json={"value": "v"}, headers=_auth_header(member_token),
    )
    assert response.status_code == 403


async def test_member_can_read_agent_long_term_memory(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]
    member_token, member = await _register(client, db_session, "member@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member)

    response = await client.get(f"/agents/{agent_id}/memory", headers=_auth_header(member_token))
    assert response.status_code == 200
    assert response.json()["memory"] == {}


async def test_manager_can_delete_agent_long_term_memory(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]
    await client.put(f"/agents/{agent_id}/memory/k", json={"value": "v"}, headers=_auth_header(owner_token))

    response = await client.delete(f"/agents/{agent_id}/memory/k", headers=_auth_header(owner_token))
    assert response.status_code == 204

    response = await client.get(f"/agents/{agent_id}/memory", headers=_auth_header(owner_token))
    assert response.json()["memory"] == {}


async def test_member_cannot_delete_agent_long_term_memory(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]
    member_token, member = await _register(client, db_session, "member@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member)

    response = await client.delete(f"/agents/{agent_id}/memory/k", headers=_auth_header(member_token))
    assert response.status_code == 403

"""Partie 5.3.6 -- memory configuration. Fast SQLite suite."""

import datetime as dt
import uuid

import pytest
from sqlalchemy import select

from api.config import settings
from api.models.agent_memory import AgentSession
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.security.agents import create_agent, update_agent
from api.services.agent_memory import add_to_memory
from api.services.agent_memory_config import (
    AgentMemoryConfigError, clear_agent_memory, get_agent_memory_config, get_default_memory_config,
    get_memory_usage, set_agent_memory_config, validate_memory_config,
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


# --------------------------------------- validate_memory_config / get_default_memory_config --


def test_get_default_memory_config_reuses_real_established_defaults():
    """Validation criterion: les défauts réutilisent Partie 5.1.11."""
    config = get_default_memory_config()
    assert config["memory_ttl"] == settings.AGENT_MEMORY_TTL
    assert config["memory_max_items"] == settings.AGENT_MEMORY_SIZE
    assert config["memory_retention_policy"] == "fifo"


def test_validate_memory_config_accepts_a_real_valid_config():
    validate_memory_config({"memory_window_size": 5, "memory_ttl": 60, "memory_max_items": 10, "memory_retention_policy": "fifo"})


@pytest.mark.parametrize("field", ["memory_window_size", "memory_ttl", "memory_max_items"])
def test_validate_memory_config_rejects_a_non_positive_value(field):
    """Validation criterion: robustesse -- valeurs invalides rejetées."""
    with pytest.raises(AgentMemoryConfigError):
        validate_memory_config({field: 0})


def test_validate_memory_config_rejects_an_unknown_retention_policy():
    with pytest.raises(AgentMemoryConfigError, match="Unknown memory_retention_policy"):
        validate_memory_config({"memory_retention_policy": "lru"})


# --------------------------------------- get/set_agent_memory_config --


async def test_get_agent_memory_config_returns_real_defaults_when_unconfigured(db_session):
    """Validation criterion: la configuration de la mémoire est correcte."""
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()

    config = await get_agent_memory_config(db_session, agent.id)
    assert config["memory_ttl"] == settings.AGENT_MEMORY_TTL
    assert config["memory_retention_policy"] == "fifo"


async def test_set_agent_memory_config_persists_real_values(db_session):
    """Validation criterion: cohérence -- la configuration est appliquée."""
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()

    await set_agent_memory_config(db_session, agent.id, memory_ttl=120, memory_max_items=5)
    await db_session.commit()

    config = await get_agent_memory_config(db_session, agent.id)
    assert config["memory_ttl"] == 120
    assert config["memory_max_items"] == 5


async def test_set_agent_memory_config_rejects_an_invalid_value(db_session):
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()
    with pytest.raises(AgentMemoryConfigError):
        await set_agent_memory_config(db_session, agent.id, memory_ttl=-1)


async def test_update_agent_rejects_an_invalid_memory_config_via_generic_update(db_session):
    """Validation criterion: sécurité/robustesse -- pas de contournement via l'endpoint générique."""
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()
    with pytest.raises(AgentMemoryConfigError):
        await update_agent(db_session, agent.id, {"memory_max_items": 0})


# --------------------------------------- get_memory_usage / clear_agent_memory --


async def test_get_memory_usage_returns_zero_for_a_fresh_agent(db_session):
    """Validation criterion: le suivi d'utilisation est correct."""
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()
    usage = await get_memory_usage(db_session, agent.id)
    assert usage == {"session_count": 0, "item_count": 0}


async def test_get_memory_usage_counts_real_sessions_and_items(db_session):
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()
    session = AgentSession(agent_id=str(agent.id), expires_at=dt.datetime.now(dt.timezone.utc))
    db_session.add(session)
    await db_session.commit()
    await add_to_memory(db_session, session.id, "topic", "billing")
    await db_session.commit()

    usage = await get_memory_usage(db_session, agent.id)
    assert usage == {"session_count": 1, "item_count": 1}


async def test_clear_agent_memory_removes_real_items_across_all_sessions(db_session):
    """Validation criterion: la mémoire peut être vidée."""
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()
    session_a = AgentSession(agent_id=str(agent.id), expires_at=dt.datetime.now(dt.timezone.utc))
    session_b = AgentSession(agent_id=str(agent.id), expires_at=dt.datetime.now(dt.timezone.utc))
    db_session.add_all([session_a, session_b])
    await db_session.commit()
    await add_to_memory(db_session, session_a.id, "a", 1)
    await add_to_memory(db_session, session_b.id, "b", 2)
    await db_session.commit()

    cleared = await clear_agent_memory(db_session, agent.id)
    await db_session.commit()

    assert cleared == 2
    usage = await get_memory_usage(db_session, agent.id)
    assert usage["item_count"] == 0


async def test_clear_agent_memory_does_not_touch_another_agents_sessions(db_session):
    """Validation criterion: sécurité/isolation -- pas de fuite entre agents."""
    agent_a = await create_agent(db_session, uuid.uuid4(), {"name": "A"}, None)
    agent_b = await create_agent(db_session, uuid.uuid4(), {"name": "B"}, None)
    await db_session.commit()
    session_b = AgentSession(agent_id=str(agent_b.id), expires_at=dt.datetime.now(dt.timezone.utc))
    db_session.add(session_b)
    await db_session.commit()
    await add_to_memory(db_session, session_b.id, "k", "v")
    await db_session.commit()

    cleared = await clear_agent_memory(db_session, agent_a.id)
    await db_session.commit()

    assert cleared == 0
    assert (await get_memory_usage(db_session, agent_b.id))["item_count"] == 1


# --------------------------------------- endpoints --


async def test_manager_can_update_agent_memory_config(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]

    response = await client.patch(f"/agents/{agent_id}/memory-config", json={"memory_ttl": 90}, headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["memory_ttl"] == 90


async def test_member_cannot_update_agent_memory_config(client, db_session, register_payload):
    """Validation criterion: sécurité -- les permissions sont respectées."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]
    member_token, member = await _register(client, db_session, "member@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member)

    response = await client.patch(f"/agents/{agent_id}/memory-config", json={"memory_ttl": 90}, headers=_auth_header(member_token))
    assert response.status_code == 403


async def test_update_agent_memory_config_rejects_an_invalid_value_via_endpoint(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]

    response = await client.patch(f"/agents/{agent_id}/memory-config", json={"memory_max_items": -1}, headers=_auth_header(owner_token))
    assert response.status_code == 400


async def test_get_agent_memory_config_endpoint(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]

    response = await client.get(f"/agents/{agent_id}/memory-config", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["memory_retention_policy"] == "fifo"


async def test_get_agent_memory_usage_endpoint(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]

    response = await client.get(f"/agents/{agent_id}/memory-usage", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json() == {"session_count": 0, "item_count": 0}


async def test_clear_agent_memory_endpoint(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]

    response = await client.post(f"/agents/{agent_id}/memory/clear", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json() == {"cleared_items": 0}


async def test_member_cannot_clear_agent_memory(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]
    member_token, member = await _register(client, db_session, "member@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member)

    response = await client.post(f"/agents/{agent_id}/memory/clear", headers=_auth_header(member_token))
    assert response.status_code == 403


async def test_create_agent_rejects_an_invalid_memory_config(client, db_session, register_payload):
    """Validation criterion: sécurité -- create_agent lui-même est protégé."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(
        f"/organizations/{org['id']}/agents", json={"name": "Bot", "memory_ttl": 0}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 400

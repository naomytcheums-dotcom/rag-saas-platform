"""Partie 5.3.10 -- agent API keys (deployment). Fast SQLite suite."""

import datetime as dt
import uuid
from unittest.mock import AsyncMock

import litellm
import pytest
from litellm.types.utils import Choices, Message, ModelResponse
from sqlalchemy import select

from api.config import settings
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.security.agents import create_agent
from api.services.agent_api_keys import (
    AgentAPIKeyError, generate_api_key, get_agent_from_api_key, hash_api_key, list_api_keys, revoke_api_key,
    validate_scopes, verify_api_key,
)


def _real_response(text: str) -> ModelResponse:
    message = Message(content=text, role="assistant")
    choice = Choices(message=message, index=0, finish_reason="stop")
    return ModelResponse(choices=[choice])


@pytest.fixture(autouse=True)
def _configure_key(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")


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


# --------------------------------------- hash_api_key / validate_scopes --


def test_hash_api_key_is_deterministic_and_real_sha256():
    """Validation criterion: sécurité -- la clé est hashée."""
    digest = hash_api_key("ak_something")
    assert digest == hash_api_key("ak_something")
    assert len(digest) == 64  # real SHA-256 hex digest length


def test_validate_scopes_accepts_real_known_scopes():
    validate_scopes(["read", "execute"])


def test_validate_scopes_rejects_an_empty_list():
    with pytest.raises(AgentAPIKeyError, match="At least one"):
        validate_scopes([])


def test_validate_scopes_rejects_an_unknown_scope():
    with pytest.raises(AgentAPIKeyError, match="Unknown scope"):
        validate_scopes(["fly"])


# --------------------------------------- generate/verify/revoke --


async def test_generate_api_key_returns_a_real_plaintext_key_once(db_session):
    """Validation criterion: la génération de clé fonctionne."""
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()

    row, plaintext_key = await generate_api_key(db_session, agent.id, "Production", ["read", "execute"])
    await db_session.commit()

    assert plaintext_key.startswith("ak_")
    assert row.key_hash == hash_api_key(plaintext_key)


async def test_generate_api_key_rejects_invalid_scopes(db_session):
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()
    with pytest.raises(AgentAPIKeyError):
        await generate_api_key(db_session, agent.id, "Production", [])


async def test_verify_api_key_accepts_a_real_valid_key(db_session):
    """Validation criterion: la vérification de clé fonctionne."""
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()
    _row, plaintext_key = await generate_api_key(db_session, agent.id, "Production", ["read"])
    await db_session.commit()

    verified = await verify_api_key(db_session, plaintext_key)
    assert verified is not None
    assert verified.last_used_at is not None


async def test_verify_api_key_rejects_an_unknown_key(db_session):
    assert await verify_api_key(db_session, "ak_not-a-real-key") is None


async def test_verify_api_key_rejects_an_expired_key(db_session):
    """Validation criterion: robustesse -- que se passe-t-il si une clé expire."""
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()
    past = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)
    _row, plaintext_key = await generate_api_key(db_session, agent.id, "Production", ["read"], expires_at=past)
    await db_session.commit()

    assert await verify_api_key(db_session, plaintext_key) is None


async def test_revoke_api_key_works_and_is_idempotent(db_session):
    """Validation criterion: la révocation fonctionne."""
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()
    row, plaintext_key = await generate_api_key(db_session, agent.id, "Production", ["read"])
    await db_session.commit()

    assert await revoke_api_key(db_session, row.id) is True
    await db_session.commit()
    assert await revoke_api_key(db_session, row.id) is False
    assert await verify_api_key(db_session, plaintext_key) is None


async def test_get_agent_from_api_key_returns_the_real_agent(db_session):
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()
    _row, plaintext_key = await generate_api_key(db_session, agent.id, "Production", ["read"])
    await db_session.commit()

    resolved = await get_agent_from_api_key(db_session, plaintext_key)
    assert resolved is not None
    assert resolved.id == agent.id


async def test_list_api_keys_orders_newest_first(db_session):
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()
    first_row, _key = await generate_api_key(db_session, agent.id, "First", ["read"])
    first_row.created_at = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    await db_session.commit()
    second_row, _key = await generate_api_key(db_session, agent.id, "Second", ["read"])
    second_row.created_at = dt.datetime(2026, 1, 2, tzinfo=dt.timezone.utc)
    await db_session.commit()

    keys = await list_api_keys(db_session, agent.id)
    assert [k.name for k in keys] == ["Second", "First"]


# --------------------------------------- endpoints --


async def test_manager_can_generate_and_list_api_keys(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]

    create_response = await client.post(
        f"/agents/{agent_id}/api-keys", json={"name": "Production", "scopes": ["read", "execute"]}, headers=_auth_header(owner_token),
    )
    assert create_response.status_code == 200
    assert create_response.json()["key"].startswith("ak_")

    list_response = await client.get(f"/agents/{agent_id}/api-keys", headers=_auth_header(owner_token))
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert "key" not in list_response.json()[0]
    assert "key_hash" not in list_response.json()[0]


async def test_member_cannot_generate_api_keys(client, db_session, register_payload):
    """Validation criterion: sécurité -- les permissions sont respectées."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]
    member_token, member = await _register(client, db_session, "member@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member)

    response = await client.post(
        f"/agents/{agent_id}/api-keys", json={"name": "Production", "scopes": ["read"]}, headers=_auth_header(member_token),
    )
    assert response.status_code == 403


async def test_manager_can_revoke_an_api_key(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]
    create_response = await client.post(
        f"/agents/{agent_id}/api-keys", json={"name": "Production", "scopes": ["read"]}, headers=_auth_header(owner_token),
    )
    key_id = create_response.json()["id"]

    revoke_response = await client.delete(f"/agents/{agent_id}/api-keys/{key_id}", headers=_auth_header(owner_token))
    assert revoke_response.status_code == 204

    list_response = await client.get(f"/agents/{agent_id}/api-keys", headers=_auth_header(owner_token))
    assert list_response.json()[0]["revoked_at"] is not None


async def test_run_agent_via_api_key_works(monkeypatch, client, db_session, register_payload):
    """Validation criterion: l'exécution via API key fonctionne."""
    mock_acompletion = AsyncMock(return_value=_real_response("hello from the agent"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]
    create_response = await client.post(
        f"/agents/{agent_id}/api-keys", json={"name": "Production", "scopes": ["execute"]}, headers=_auth_header(owner_token),
    )
    real_key = create_response.json()["key"]

    run_response = await client.post("/api/agents/run", json={"input": "hi"}, headers={"X-API-Key": real_key})
    assert run_response.status_code == 200
    assert run_response.json()["status"] == "completed"
    assert run_response.json()["result"] == "hello from the agent"


async def test_run_agent_via_api_key_rejects_an_invalid_key(client, db_session):
    response = await client.post("/api/agents/run", json={"input": "hi"}, headers={"X-API-Key": "ak_not-a-real-key"})
    assert response.status_code == 401


async def test_run_agent_via_api_key_rejects_a_read_only_key(client, db_session, register_payload):
    """Validation criterion: sécurité -- une clé sans le scope execute est rejetée."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]
    create_response = await client.post(
        f"/agents/{agent_id}/api-keys", json={"name": "ReadOnly", "scopes": ["read"]}, headers=_auth_header(owner_token),
    )
    real_key = create_response.json()["key"]

    response = await client.post("/api/agents/run", json={"input": "hi"}, headers={"X-API-Key": real_key})
    assert response.status_code == 403


async def test_run_agent_via_api_key_rejects_a_revoked_key(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]
    create_response = await client.post(
        f"/agents/{agent_id}/api-keys", json={"name": "Production", "scopes": ["execute"]}, headers=_auth_header(owner_token),
    )
    key_id = create_response.json()["id"]
    real_key = create_response.json()["key"]
    await client.delete(f"/agents/{agent_id}/api-keys/{key_id}", headers=_auth_header(owner_token))

    response = await client.post("/api/agents/run", json={"input": "hi"}, headers={"X-API-Key": real_key})
    assert response.status_code == 401

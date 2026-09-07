"""Partie 5.3.3 -- LLM model selection. Fast SQLite suite."""

import uuid

import pytest
from sqlalchemy import select

from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.security.agents import create_agent
from api.services.agent_models import (
    AgentModelError, MODEL_CATALOG, get_agent_model, get_available_models, get_default_model_config,
    set_agent_model, validate_agent_model,
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


# --------------------------------------- validate_agent_model / get_available_models --


def test_validate_agent_model_accepts_a_real_known_model():
    """Validation criterion: la validation fonctionne."""
    validate_agent_model("anthropic", "claude-3-5-sonnet-20241022")  # does not raise


def test_validate_agent_model_rejects_an_unknown_provider():
    with pytest.raises(AgentModelError, match="Unknown provider"):
        validate_agent_model("not-a-provider", "x")


def test_validate_agent_model_rejects_an_unknown_model_for_a_real_provider():
    """Validation criterion: robustesse -- que se passe-t-il si le
    modèle n'est pas disponible."""
    with pytest.raises(AgentModelError, match="not in the real, known catalog"):
        validate_agent_model("anthropic", "gpt-4o")  # a real model, wrong real provider


def test_get_available_models_lists_all_real_providers():
    """Validation criterion: les modèles sont listés."""
    models = get_available_models()
    assert models == MODEL_CATALOG


def test_get_available_models_filters_by_real_provider():
    models = get_available_models("openai")
    assert models == {"openai": MODEL_CATALOG["openai"]}


def test_get_available_models_rejects_an_unknown_provider():
    with pytest.raises(AgentModelError):
        get_available_models("not-a-provider")


def test_get_default_model_config_reuses_real_established_defaults():
    config = get_default_model_config()
    assert config["provider"] == "anthropic"
    assert 0.0 <= config["temperature"] <= 2.0


# --------------------------------------- get/set_agent_model --


async def test_get_agent_model_returns_real_defaults_when_unconfigured(db_session):
    """Validation criterion: la configuration du modèle est correcte."""
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()

    config = await get_agent_model(db_session, agent.id)
    assert config["provider"] == "anthropic"


async def test_set_agent_model_persists_a_real_valid_config(db_session):
    """Validation criterion: cohérence -- la configuration du modèle
    est appliquée."""
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()

    await set_agent_model(db_session, agent.id, "openai", "gpt-4o", temperature=0.3)
    await db_session.commit()

    config = await get_agent_model(db_session, agent.id)
    assert config["provider"] == "openai"
    assert config["model"] == "gpt-4o"
    assert config["temperature"] == 0.3


async def test_set_agent_model_rejects_an_invalid_model(db_session):
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()

    with pytest.raises(AgentModelError):
        await set_agent_model(db_session, agent.id, "anthropic", "not-a-real-model")


async def test_get_agent_model_returns_none_for_unknown_agent(db_session):
    assert await get_agent_model(db_session, uuid.uuid4()) is None


# --------------------------------------- endpoints --


async def test_manager_can_update_agent_model(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]

    response = await client.patch(f"/agents/{agent_id}/model", json={"provider": "openai", "model": "gpt-4o-mini"}, headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["provider"] == "openai"


async def test_member_cannot_update_agent_model(client, db_session, register_payload):
    """Validation criterion: sécurité -- les permissions sont respectées."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]
    member_token, member = await _register(client, db_session, "member@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member)

    response = await client.patch(f"/agents/{agent_id}/model", json={"provider": "openai", "model": "gpt-4o"}, headers=_auth_header(member_token))
    assert response.status_code == 403


async def test_update_agent_model_rejects_an_invalid_model_via_endpoint(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]

    response = await client.patch(f"/agents/{agent_id}/model", json={"provider": "anthropic", "model": "not-real"}, headers=_auth_header(owner_token))
    assert response.status_code == 400


async def test_list_all_models_endpoint(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    response = await client.get("/models", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert "anthropic" in response.json()


async def test_list_provider_models_endpoint(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    response = await client.get("/models/mistral", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert "mistral" in response.json()

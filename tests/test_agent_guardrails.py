"""Partie 5.3.9 -- agent guardrails. Fast SQLite suite."""

import uuid

import pytest
from sqlalchemy import select

from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.security.agents import create_agent, update_agent
from api.services.agent_guardrails import (
    AgentGuardrailError, check_blocked_topics, check_content_safety, check_domain_whitelist,
    get_agent_guardrails, set_agent_guardrails, validate_guardrails, validate_guardrails_config, validate_output_length,
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


# --------------------------------------- validate_guardrails_config --


def test_validate_guardrails_config_accepts_a_real_valid_config():
    validate_guardrails_config({"content_filter_level": "high", "max_tokens_per_response": 500, "blocked_topics": ["politics"]})


def test_validate_guardrails_config_rejects_an_unknown_filter_level():
    with pytest.raises(AgentGuardrailError, match="Unknown content_filter_level"):
        validate_guardrails_config({"content_filter_level": "extreme"})


def test_validate_guardrails_config_rejects_a_non_positive_max_tokens():
    with pytest.raises(AgentGuardrailError):
        validate_guardrails_config({"max_tokens_per_response": 0})


def test_validate_guardrails_config_rejects_a_non_list_blocked_topics():
    with pytest.raises(AgentGuardrailError):
        validate_guardrails_config({"blocked_topics": "politics"})


# --------------------------------------- check_blocked_topics --


async def test_check_blocked_topics_finds_a_real_configured_topic(db_session):
    """Validation criterion: les sujets interdits sont bloqués."""
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot", "blocked_topics": ["politics", "religion"]}, None)
    await db_session.commit()

    assert await check_blocked_topics(db_session, agent.id, "Let's talk about politics today") == ["politics"]


async def test_check_blocked_topics_returns_empty_when_unconfigured(db_session):
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()
    assert await check_blocked_topics(db_session, agent.id, "anything goes") == []


# --------------------------------------- check_content_safety --


async def test_check_content_safety_flags_a_real_unsafe_phrase(db_session):
    """Validation criterion: robustesse -- contenu dangereux détecté."""
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot", "content_filter_level": "low"}, None)
    await db_session.commit()

    matched = await check_content_safety(db_session, agent.id, "here is how to make a bomb")
    assert "low" in matched


async def test_check_content_safety_passes_safe_text(db_session):
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()
    assert await check_content_safety(db_session, agent.id, "what a lovely day for a walk") == []


async def test_check_content_safety_respects_filter_level_gating(db_session):
    """Validation criterion: un niveau bas ne détecte pas les catégories plus élevées."""
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot", "content_filter_level": "low"}, None)
    await db_session.commit()
    assert await check_content_safety(db_session, agent.id, "how to commit suicide") == []


# --------------------------------------- check_domain_whitelist --


async def test_check_domain_whitelist_allows_all_when_unconfigured(db_session):
    """Validation criterion: les domaines autorisés sont respectés (opt-in)."""
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()
    assert await check_domain_whitelist(db_session, agent.id, "https://anything.example.com/page") is True


async def test_check_domain_whitelist_allows_a_configured_domain_and_its_subdomains(db_session):
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot", "allowed_domains": ["acme.com"]}, None)
    await db_session.commit()
    assert await check_domain_whitelist(db_session, agent.id, "https://docs.acme.com/page") is True


async def test_check_domain_whitelist_rejects_a_non_allowed_domain(db_session):
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot", "allowed_domains": ["acme.com"]}, None)
    await db_session.commit()
    assert await check_domain_whitelist(db_session, agent.id, "https://evil.example.com/page") is False


# --------------------------------------- validate_output_length --


async def test_validate_output_length_passes_when_unconfigured(db_session):
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()
    assert await validate_output_length(db_session, agent.id, "a" * 10000) is True


async def test_validate_output_length_rejects_an_over_long_output(db_session):
    """Validation criterion: les longueurs sont validées."""
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot", "max_tokens_per_response": 3}, None)
    await db_session.commit()
    assert await validate_output_length(db_session, agent.id, "one two three four") is False
    assert await validate_output_length(db_session, agent.id, "one two three") is True


# --------------------------------------- validate_guardrails --


async def test_validate_guardrails_passes_clean_input_and_output(db_session):
    """Validation criterion: les garde-fous fonctionnent."""
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot", "blocked_topics": ["politics"]}, None)
    await db_session.commit()
    result = await validate_guardrails(db_session, agent.id, "hello", "hi there, how can I help?")
    assert result == {"passed": True, "violations": []}


async def test_validate_guardrails_fails_on_a_blocked_topic_in_the_output(db_session):
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot", "blocked_topics": ["politics"]}, None)
    await db_session.commit()
    result = await validate_guardrails(db_session, agent.id, "hello", "let's discuss politics")
    assert result["passed"] is False
    assert any("blocked_topic" in v for v in result["violations"])


async def test_validate_guardrails_is_a_real_no_op_when_disabled(db_session):
    """Validation criterion: robustesse -- guardrails_enabled=False ne bloque rien."""
    agent = await create_agent(
        db_session, uuid.uuid4(), {"name": "Bot", "blocked_topics": ["politics"], "guardrails_enabled": False}, None,
    )
    await db_session.commit()
    result = await validate_guardrails(db_session, agent.id, "hello", "let's discuss politics")
    assert result == {"passed": True, "violations": []}


# --------------------------------------- get/set_agent_guardrails --


async def test_set_agent_guardrails_persists_real_values(db_session):
    """Validation criterion: cohérence -- la configuration est appliquée."""
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()

    await set_agent_guardrails(db_session, agent.id, blocked_topics=["politics"], content_filter_level="high")
    await db_session.commit()

    config = await get_agent_guardrails(db_session, agent.id)
    assert config["blocked_topics"] == ["politics"]
    assert config["content_filter_level"] == "high"


async def test_set_agent_guardrails_rejects_an_invalid_value(db_session):
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()
    with pytest.raises(AgentGuardrailError):
        await set_agent_guardrails(db_session, agent.id, content_filter_level="extreme")


async def test_update_agent_rejects_an_invalid_guardrails_config_via_generic_update(db_session):
    """Validation criterion: sécurité -- pas de contournement via l'endpoint générique."""
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()
    with pytest.raises(AgentGuardrailError):
        await update_agent(db_session, agent.id, {"max_tokens_per_response": -1})


# --------------------------------------- endpoints --


async def test_manager_can_update_agent_guardrails(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]

    response = await client.patch(f"/agents/{agent_id}/guardrails", json={"blocked_topics": ["politics"]}, headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["blocked_topics"] == ["politics"]


async def test_member_cannot_update_agent_guardrails(client, db_session, register_payload):
    """Validation criterion: sécurité -- les permissions sont respectées."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]
    member_token, member = await _register(client, db_session, "member@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member)

    response = await client.patch(f"/agents/{agent_id}/guardrails", json={"blocked_topics": ["politics"]}, headers=_auth_header(member_token))
    assert response.status_code == 403


async def test_update_agent_guardrails_rejects_an_invalid_value_via_endpoint(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]

    response = await client.patch(f"/agents/{agent_id}/guardrails", json={"content_filter_level": "extreme"}, headers=_auth_header(owner_token))
    assert response.status_code == 400


async def test_get_agent_guardrails_endpoint(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]

    response = await client.get(f"/agents/{agent_id}/guardrails", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["content_filter_level"] == "medium"


async def test_create_agent_rejects_an_invalid_guardrails_config(client, db_session, register_payload):
    """Validation criterion: sécurité -- create_agent lui-même est protégé."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(
        f"/organizations/{org['id']}/agents", json={"name": "Bot", "content_filter_level": "extreme"}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 400

"""Partie 5.3.2 -- system prompt templating. Pure functions tested
directly, plus endpoint tests."""

import uuid

from sqlalchemy import select

from api.config import settings
from api.models.agent import Agent
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.services.agent_prompts import (
    KNOWN_VARIABLES, get_system_prompt_variables, preview_system_prompt, render_system_prompt, validate_system_prompt,
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


def _make_agent(**overrides) -> Agent:
    defaults = {
        "organization_id": uuid.uuid4(), "name": "Bot", "system_prompt": "You are a helpful assistant.",
        "model_config_json": {}, "tools": [],
    }
    defaults.update(overrides)
    return Agent(**defaults)


# --------------------------------------- render_system_prompt --


def test_render_system_prompt_substitutes_real_variables():
    """Validation criterion: le rendu du prompt fonctionne, les
    variables sont remplacées."""
    agent = _make_agent(system_prompt_template="You help {{user_name}} at {{organization_name}}.")
    rendered = render_system_prompt(agent, {"user_name": "Ada", "organization_name": "Acme"})
    assert rendered == "You help Ada at Acme."


def test_render_system_prompt_fills_real_date_and_time_automatically():
    agent = _make_agent(system_prompt_template="Today is {{date}}.")
    rendered = render_system_prompt(agent)
    import datetime as dt
    assert dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d") in rendered


def test_render_system_prompt_leaves_a_real_missing_variable_as_a_placeholder():
    """Validation criterion: robustesse -- que se passe-t-il si une
    variable est manquante."""
    agent = _make_agent(system_prompt_template="Hello {{user_name}}.")
    rendered = render_system_prompt(agent, {})
    assert rendered == "Hello {{user_name}}."


def test_render_system_prompt_falls_back_to_plain_system_prompt_without_a_template():
    agent = _make_agent(system_prompt="Plain prompt, no template.")
    assert render_system_prompt(agent) == "Plain prompt, no template."


def test_render_system_prompt_rejects_no_real_code_execution_via_format():
    """Validation criterion: sécurité -- pas d'injection via le
    mécanisme de rendu (le remplacement est un simple regex, jamais
    str.format())."""
    agent = _make_agent(system_prompt_template="{0.__class__.__init__.__globals__}")
    rendered = render_system_prompt(agent)
    assert rendered == "{0.__class__.__init__.__globals__}"  # untouched -- not a real {{var}} pattern


def test_preview_system_prompt_matches_render(monkeypatch):
    agent = _make_agent(system_prompt_template="Hi {{user_name}}")
    assert preview_system_prompt(agent, {"user_name": "Ada"}) == render_system_prompt(agent, {"user_name": "Ada"})


# --------------------------------------- validate_system_prompt --


def test_validate_system_prompt_accepts_a_real_valid_prompt():
    """Validation criterion: les templates sont validés."""
    assert validate_system_prompt("You are a helpful assistant, {{user_name}}.") == []


def test_validate_system_prompt_rejects_an_empty_prompt():
    assert validate_system_prompt("") != []


def test_validate_system_prompt_rejects_a_prompt_over_the_real_max_length(monkeypatch):
    monkeypatch.setattr(settings, "SYSTEM_PROMPT_MAX_LENGTH", 10)
    errors = validate_system_prompt("x" * 100)
    assert any("maximum length" in e for e in errors)


def test_validate_system_prompt_rejects_an_unknown_variable():
    errors = validate_system_prompt("Hello {{not_a_real_variable}}")
    assert any("Unknown template variables" in e for e in errors)


# --------------------------------------- get_system_prompt_variables --


def test_get_system_prompt_variables_returns_the_real_known_set():
    agent = _make_agent()
    assert get_system_prompt_variables(agent) == list(KNOWN_VARIABLES)


# --------------------------------------- endpoints --


async def test_member_can_preview_system_prompt(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(
        f"/organizations/{org['id']}/agents",
        json={"name": "Bot", "system_prompt": "You help {{user_name}} at {{organization_name}}."},
        headers=_auth_header(owner_token),
    )
    agent_id = created.json()["id"]

    response = await client.get(f"/agents/{agent_id}/system-prompt/preview", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert "Acme" in response.json()["rendered"]


async def test_manager_can_update_system_prompt(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]

    response = await client.patch(
        f"/agents/{agent_id}/system-prompt", json={"system_prompt_template": "New template {{date}}"}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 200


async def test_member_cannot_update_system_prompt(client, db_session, register_payload):
    """Validation criterion: sécurité -- les permissions sont respectées."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]
    member_token, member = await _register(client, db_session, "member@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member)

    response = await client.patch(f"/agents/{agent_id}/system-prompt", json={"system_prompt": "x"}, headers=_auth_header(member_token))
    assert response.status_code == 403


async def test_get_system_prompt_variables_endpoint(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]

    response = await client.get(f"/agents/{agent_id}/system-prompt/variables", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert "user_name" in response.json()["variables"]

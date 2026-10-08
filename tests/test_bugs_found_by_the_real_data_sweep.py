"""Regression tests for bugs the real-data sweep (tests/test_sweep_with_real_data.py) found: routes that crashed on every call."""

import inspect
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def _owner(client, register_payload):
    token = (await client.post("/auth/register", json={"email": register_payload["email"], "password": register_payload["password"], "accept_terms": True})).json()["access_token"]
    org_id = (await client.post("/organizations", json={"name": "Bugs"}, headers=_auth(token))).json()["id"]
    return token, org_id


async def test_agent_api_key_with_an_unknown_scope_is_a_400_not_an_unhandled_exception(client, register_payload):
    token, org_id = await _owner(client, register_payload)
    agent = await client.post(f"/organizations/{org_id}/agents", json={"name": "A", "system_prompt": "p"}, headers=_auth(token))
    if agent.status_code not in (200, 201):
        pytest.skip(f"could not create an agent in this test setup: {agent.status_code} {agent.text[:120]}")
    response = await client.post(f"/agents/{agent.json()['id']}/api-keys", json={"name": "k", "scopes": ["nope"]}, headers=_auth(token))
    assert response.status_code == 400 and "scope" in response.json()["detail"].lower()


def test_the_monday_import_route_uses_the_error_class_the_service_really_defines():
    """It imported a `MondayError` the service never defined, so the route raised ImportError on every call."""
    import importlib

    module = importlib.import_module("api.services.monday_extraction")
    assert hasattr(module, "MondaycomError") and hasattr(module, "fetch_monday_records")

    import api.routers.crm as crm

    assert "MondaycomError as MondayError" in inspect.getsource(crm.import_monday)


async def test_monday_import_reports_a_provider_failure_as_502(client, register_payload, monkeypatch):
    from api.config import settings
    from api.services.monday_extraction import MondaycomError

    monkeypatch.setattr(settings, "MONDAY_ENABLED", True)
    monkeypatch.setattr("api.services.monday_extraction.fetch_monday_records", AsyncMock(side_effect=MondaycomError("API token not configured")))
    token, org_id = await _owner(client, register_payload)
    response = await client.post(f"/organizations/{org_id}/crm/monday/import", json={"limit": 5}, headers=_auth(token))
    assert response.status_code == 502


async def test_send_test_notification_calls_create_notification_with_its_real_signature(monkeypatch):
    """It passed type/title/body/data, keywords create_notification never had: a TypeError on every call."""
    from api.security import notifications as security_notifications

    org_id, user_id = uuid.uuid4(), uuid.uuid4()
    monkeypatch.setattr(security_notifications, "preview_notification_template", AsyncMock(return_value={"title": "t", "body": "b"}))
    create = AsyncMock(return_value=MagicMock())
    monkeypatch.setattr("api.services.notifications.create_notification", create)

    await security_notifications.send_test_notification(MagicMock(), org_id, user_id, "invitation_accepted", {"who": "Ada"})

    create.assert_awaited_once()
    assert create.await_args.kwargs == {"organization_id": org_id, "user_id": user_id, "notification_type": "invitation_accepted", "context": {"who": "Ada"}}


async def test_long_term_memory_extraction_uses_the_projects_own_llm_layer_by_default(monkeypatch):
    from api.services import agent_long_term_memory as ltm

    captured = {}

    async def fake_chat_completion(messages, **kwargs):
        captured["messages"], captured["kwargs"] = messages, kwargs
        return '{"preferred_language": "French"}'

    stored = {}

    async def fake_set(db, agent_id, key, value, **kwargs):
        stored[key] = value

    monkeypatch.setattr("api.services.llm_providers.chat_completion", fake_chat_completion)
    monkeypatch.setattr(ltm, "set_long_term_memory", fake_set)
    out = await ltm.extract_and_store_long_term_memory(MagicMock(), uuid.uuid4(), user_id=uuid.uuid4(), user_message="Reply in French please", assistant_message="Bien sur")

    assert out == {"preferred_language": "French"} and stored == {"preferred_language": "French"}
    assert captured["kwargs"]["temperature"] == 0.0 and captured["messages"][0]["role"] == "user"


def test_automatic_memory_extraction_is_opt_in_because_it_costs_an_extra_llm_call():
    from api.config import settings

    assert settings.AGENT_MEMORY_AUTO_EXTRACT is False


async def test_template_preview_and_test_with_a_context_missing_a_variable_are_400(client, register_payload):
    """The template uses {{ greeting }}; a context without it used to raise jinja2.UndefinedError (HTTP 500)."""
    token, org_id = await _owner(client, register_payload)
    template = await client.post(
        f"/organizations/{org_id}/notifications/templates",
        json={"notification_type": "custom_sweep", "title": "{{ greeting }}", "body": "{{ detail }}"}, headers=_auth(token),
    )
    if template.status_code not in (200, 201):
        pytest.skip(f"could not create a template in this test setup: {template.status_code} {template.text[:160]}")
    for suffix in ("preview", "test"):
        response = await client.post(
            f"/organizations/{org_id}/notifications/templates/{suffix}", json={"notification_type": "custom_sweep", "context": {}}, headers=_auth(token),
        )
        assert response.status_code == 400 and "cannot be rendered" in response.json()["detail"]

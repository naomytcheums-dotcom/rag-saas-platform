"""Partie 5.4.11 -- Calendar workflow block. Real httpx.MockTransport
at the Google/Outlook boundary, same precedent as
tests/test_calendar_tools.py."""

import httpx
import pytest

from api.config import settings
from api.services.workflow_block_calendar import (
    execute_calendar_block, format_calendar_results, render_calendar_field, validate_calendar_config,
)
from api.services.workflow_blocks import WorkflowBlockError


def _patch_client(monkeypatch, handler):
    monkeypatch.setattr("api.tools.calendar_tools._client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))


@pytest.fixture(autouse=True)
def _configure_credentials(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CALENDAR_REFRESH_TOKEN", "google-refresh")
    monkeypatch.setattr(settings, "GOOGLE_CALENDAR_CLIENT_ID", "google-client")
    monkeypatch.setattr(settings, "GOOGLE_CALENDAR_CLIENT_SECRET", "google-secret")
    import api.tools.calendar_tools as mod
    mod._access_token_cache.clear()


def _token_response() -> httpx.Response:
    return httpx.Response(200, json={"access_token": "real-access-token", "expires_in": 3600})


def _dispatch(api_response):
    def handler(request: httpx.Request) -> httpx.Response:
        if "oauth2.googleapis.com" in str(request.url):
            return _token_response()
        return api_response(request)
    return handler


# --------------------------------------- validate_calendar_config / render_calendar_field --


def test_validate_calendar_config_accepts_a_real_valid_create_config():
    validate_calendar_config({"action": "create", "provider": "google", "title": "Meeting", "start_time": "t0", "end_time": "t1"})


def test_validate_calendar_config_rejects_an_unknown_action():
    """Validation criterion: la validation fonctionne."""
    with pytest.raises(WorkflowBlockError, match="Unknown action"):
        validate_calendar_config({"action": "not-real", "provider": "google"})


def test_validate_calendar_config_rejects_create_without_required_fields():
    with pytest.raises(WorkflowBlockError, match="'create' action requires"):
        validate_calendar_config({"action": "create", "provider": "google"})


def test_validate_calendar_config_rejects_update_without_event_id():
    with pytest.raises(WorkflowBlockError, match="event_id"):
        validate_calendar_config({"action": "update", "provider": "google"})


def test_validate_calendar_config_rejects_find_slots_without_duration():
    with pytest.raises(WorkflowBlockError, match="duration"):
        validate_calendar_config({"action": "find_slots", "provider": "google", "start_time": "t0", "end_time": "t1"})


def test_render_calendar_field_substitutes_real_variables():
    """Validation criterion: le rendu des champs fonctionne."""
    assert render_calendar_field("Meeting with {{name}}", {"name": "Ada"}) == "Meeting with Ada"


def test_format_calendar_results_wraps_the_real_value():
    assert format_calendar_results([{"id": "evt1"}]) == {"results": [{"id": "evt1"}]}


# --------------------------------------- execute_calendar_block --


async def test_execute_calendar_block_lists_real_events(monkeypatch):
    """Validation criterion: l'exécution du bloc Calendar fonctionne (list)."""
    def api_response(request):
        return httpx.Response(200, json={"items": [{"id": "evt1", "summary": "Standup", "start": {"dateTime": "2026-01-01T09:00:00Z"}, "end": {"dateTime": "2026-01-01T09:30:00Z"}}]})

    _patch_client(monkeypatch, _dispatch(api_response))
    result = await execute_calendar_block(
        {"action": "list", "provider": "google", "start_time": "2026-01-01T00:00:00Z", "end_time": "2026-01-02T00:00:00Z", "output_key": "events"}, {},
    )
    assert result["events"]["results"][0]["title"] == "Standup"


async def test_execute_calendar_block_creates_a_real_event_with_rendered_fields(monkeypatch):
    """Validation criterion: cohérence -- réutilise les vrais outils calendrier (5.2.7)."""
    def api_response(request):
        import json
        payload = json.loads(request.read())
        assert payload["summary"] == "Meeting with Ada"
        return httpx.Response(200, json={"id": "evt2", "summary": payload["summary"], "start": {"dateTime": "t0"}, "end": {"dateTime": "t1"}})

    _patch_client(monkeypatch, _dispatch(api_response))
    result = await execute_calendar_block(
        {"action": "create", "provider": "google", "title": "Meeting with {{name}}", "start_time": "t0", "end_time": "t1"}, {"name": "Ada"},
    )
    assert result["output"]["results"]["title"] == "Meeting with Ada"


async def test_execute_calendar_block_deletes_a_real_event(monkeypatch):
    def api_response(request):
        return httpx.Response(204)

    _patch_client(monkeypatch, _dispatch(api_response))
    result = await execute_calendar_block({"action": "delete", "provider": "google", "event_id": "evt1"}, {})
    assert result["output"]["results"] is True


async def test_execute_calendar_block_raises_on_invalid_config():
    """Validation criterion: robustesse -- erreurs gérées."""
    with pytest.raises(WorkflowBlockError):
        await execute_calendar_block({}, {})


async def test_execute_calendar_block_wraps_a_real_calendar_failure(monkeypatch):
    def api_response(request):
        return httpx.Response(500, text="server error")

    _patch_client(monkeypatch, _dispatch(api_response))
    with pytest.raises(WorkflowBlockError, match="calendar block failed"):
        await execute_calendar_block(
            {"action": "list", "provider": "google", "start_time": "t0", "end_time": "t1"}, {},
        )

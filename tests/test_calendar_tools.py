"""Partie 5.2.7 -- calendar tools (Google, Outlook). Real
httpx.MockTransport -- real request/response parsing, fake network
transport, same precedent as tests/test_github_extraction.py."""

import httpx
import pytest

from api.config import settings
from api.tools.calendar_tools import (
    CalendarError, calendar_create_event, calendar_delete_event, calendar_find_available_slots, calendar_get_event,
    calendar_list_events, calendar_update_event,
)


def _patch_client(monkeypatch, handler):
    monkeypatch.setattr("api.tools.calendar_tools._client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))


@pytest.fixture(autouse=True)
def _configure_credentials(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CALENDAR_REFRESH_TOKEN", "google-refresh")
    monkeypatch.setattr(settings, "GOOGLE_CALENDAR_CLIENT_ID", "google-client")
    monkeypatch.setattr(settings, "GOOGLE_CALENDAR_CLIENT_SECRET", "google-secret")
    monkeypatch.setattr(settings, "OUTLOOK_CALENDAR_REFRESH_TOKEN", "outlook-refresh")
    monkeypatch.setattr(settings, "OUTLOOK_CALENDAR_CLIENT_ID", "outlook-client")
    monkeypatch.setattr(settings, "OUTLOOK_CALENDAR_CLIENT_SECRET", "outlook-secret")
    import api.tools.calendar_tools as mod
    mod._access_token_cache.clear()


def _token_response() -> httpx.Response:
    return httpx.Response(200, json={"access_token": "real-access-token", "expires_in": 3600})


def _dispatch(token_url_host: str, token_response, api_response):
    def handler(request: httpx.Request) -> httpx.Response:
        if token_url_host in str(request.url):
            return token_response
        return api_response(request)
    return handler


# --------------------------------------- calendar_list_events --


async def test_calendar_list_events_google_returns_a_real_unified_shape(monkeypatch):
    """Validation criterion: les appels calendrier fonctionnent (mock)."""
    def api_response(request):
        assert request.headers["Authorization"] == "Bearer real-access-token"
        return httpx.Response(200, json={"items": [{"id": "evt1", "summary": "Standup", "start": {"dateTime": "2026-01-01T09:00:00Z"}, "end": {"dateTime": "2026-01-01T09:30:00Z"}}]})

    _patch_client(monkeypatch, _dispatch("oauth2.googleapis.com", _token_response(), api_response))
    events = await calendar_list_events("google", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z")
    assert events[0]["title"] == "Standup"


async def test_calendar_list_events_outlook_returns_a_real_unified_shape(monkeypatch):
    def api_response(request):
        return httpx.Response(200, json={"value": [{"id": "evt2", "subject": "Review", "start": {"dateTime": "2026-01-01T10:00:00Z"}, "end": {"dateTime": "2026-01-01T10:30:00Z"}}]})

    _patch_client(monkeypatch, _dispatch("login.microsoftonline.com", _token_response(), api_response))
    events = await calendar_list_events("outlook", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z")
    assert events[0]["title"] == "Review"


async def test_calendar_list_events_rejects_an_unknown_provider(monkeypatch):
    with pytest.raises(CalendarError, match="Unknown calendar provider"):
        await calendar_list_events("zoom", "2026-01-01", "2026-01-02")


async def test_calendar_list_events_raises_without_a_real_refresh_token(monkeypatch):
    """Validation criterion: sécurité -- les tokens sont requis."""
    monkeypatch.setattr(settings, "GOOGLE_CALENDAR_REFRESH_TOKEN", "")
    with pytest.raises(CalendarError, match="GOOGLE_CALENDAR_REFRESH_TOKEN"):
        await calendar_list_events("google", "2026-01-01", "2026-01-02")


async def test_calendar_authentication_failure_raises_a_real_error(monkeypatch):
    """Validation criterion: robustesse -- les erreurs API sont gérées."""
    def handler(request):
        return httpx.Response(400, json={"error": "invalid_grant", "error_description": "Token expired"})

    _patch_client(monkeypatch, handler)
    with pytest.raises(CalendarError, match="invalid_grant"):
        await calendar_list_events("google", "2026-01-01", "2026-01-02")


# --------------------------------------- create / update / delete / get --


async def test_calendar_create_event_google(monkeypatch):
    def api_response(request):
        import json
        body = json.loads(request.read())
        assert body["summary"] == "Team sync"
        assert body["attendees"] == [{"email": "a@example.com"}]
        return httpx.Response(200, json={"id": "new-evt", "summary": "Team sync"})

    _patch_client(monkeypatch, _dispatch("oauth2.googleapis.com", _token_response(), api_response))
    event = await calendar_create_event("google", "Team sync", "2026-01-01T09:00:00Z", "2026-01-01T09:30:00Z", attendees=["a@example.com"])
    assert event["id"] == "new-evt"


async def test_calendar_update_event_sends_only_real_given_fields(monkeypatch):
    def api_response(request):
        import json
        body = json.loads(request.read())
        assert body == {"subject": "Updated title"}
        return httpx.Response(200, json={"id": "evt1", "subject": "Updated title"})

    _patch_client(monkeypatch, _dispatch("login.microsoftonline.com", _token_response(), api_response))
    result = await calendar_update_event("outlook", "evt1", title="Updated title")
    assert result["subject"] == "Updated title"


async def test_calendar_delete_event_returns_true(monkeypatch):
    _patch_client(monkeypatch, _dispatch("oauth2.googleapis.com", _token_response(), lambda r: httpx.Response(204)))
    assert await calendar_delete_event("google", "evt1") is True


async def test_calendar_get_event(monkeypatch):
    _patch_client(monkeypatch, _dispatch("oauth2.googleapis.com", _token_response(), lambda r: httpx.Response(200, json={"id": "evt1", "summary": "x"})))
    event = await calendar_get_event("google", "evt1")
    assert event["id"] == "evt1"


# --------------------------------------- find_available_slots --


async def test_calendar_find_available_slots_returns_real_gaps(monkeypatch):
    def api_response(request):
        return httpx.Response(200, json={"items": [{"id": "e1", "summary": "busy", "start": {"dateTime": "2026-01-01T10:00:00+00:00"}, "end": {"dateTime": "2026-01-01T11:00:00+00:00"}}]})

    _patch_client(monkeypatch, _dispatch("oauth2.googleapis.com", _token_response(), api_response))
    slots = await calendar_find_available_slots("google", "2026-01-01T09:00:00+00:00", "2026-01-01T12:00:00+00:00", duration=30)
    assert len(slots) == 2  # before and after the one busy block
    assert slots[0]["start"] == "2026-01-01T09:00:00+00:00"

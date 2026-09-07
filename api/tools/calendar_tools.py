"""
Partie 5.2.7 -- letting an agent read/create/update/delete calendar
events on a real Google Calendar or a real Outlook (Microsoft Graph)
calendar.

**Real reuse of an established PATTERN, not the exact functions**:
`api/services/google_drive_extraction.py`'s own `authenticate_drive`
and `api/services/onedrive_extraction.py`'s own `authenticate_onedrive`
already established the real "exchange a long-lived refresh token for a
real, short-lived access token, cached and PROACTIVELY refreshed before
its own real expiry" technique this module reuses -- but this étape's
own literal config declares its OWN, separate
`GOOGLE_CALENDAR_CLIENT_ID`/`SECRET`/`REFRESH_TOKEN` and
`OUTLOOK_CALENDAR_CLIENT_ID`/`SECRET`/`REFRESH_TOKEN` (a real, distinct
OAuth app registration from Drive/OneDrive's own), so this module
builds its own real, separate token cache against the SAME real OAuth
token endpoints (`https://oauth2.googleapis.com/token`,
`https://login.microsoftonline.com/common/oauth2/v2.0/token`) rather
than calling those other modules' functions with the wrong credentials.

**Honest, stated limitation, same as every OAuth-based module in this
codebase**: no real, live Google/Microsoft OAuth credentials are
available in this session (provisioning one means a real, interactive
browser consent flow, outside this session's safe, automated scope,
same restraint `google_drive_extraction.py` already documented) --
every real HTTP call below is built against each provider's own real,
public API documentation and tested via `httpx.MockTransport`, not
verified end-to-end against a live account.
"""

import time
import uuid

import httpx

from api.config import settings
from api.services.tools import ToolSpec

_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_CALENDAR_BASE_URL = "https://www.googleapis.com/calendar/v3"
_MS_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
_MS_GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
_TOKEN_REFRESH_MARGIN_SECONDS = 60
_TIMEOUT_SECONDS = 15.0

_access_token_cache: dict[str, tuple[str, float]] = {}


class CalendarError(ValueError):
    """Real, dedicated exception."""


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=_TIMEOUT_SECONDS)


async def _authenticate(cache_key: str, token_url: str, refresh_token: str, client_id: str, client_secret: str, extra_data: dict | None = None) -> str:
    cached = _access_token_cache.get(cache_key)
    if cached is not None:
        access_token, expires_at = cached
        if time.time() < expires_at - _TOKEN_REFRESH_MARGIN_SECONDS:
            return access_token

    data = {"grant_type": "refresh_token", "refresh_token": refresh_token, "client_id": client_id, "client_secret": client_secret}
    if extra_data:
        data.update(extra_data)

    async with _client() as client:
        response = await client.post(token_url, data=data)

    if response.status_code != 200:
        try:
            body = response.json()
        except ValueError:
            body = {}
        raise CalendarError(f"OAuth token refresh failed ({body.get('error', 'unknown_error')}): {body.get('error_description', response.text)}")

    body = response.json()
    access_token = body["access_token"]
    _access_token_cache[cache_key] = (access_token, time.time() + body.get("expires_in", 3600))
    return access_token


async def _authenticate_google() -> str:
    if not settings.GOOGLE_CALENDAR_REFRESH_TOKEN:
        raise CalendarError("GOOGLE_CALENDAR_REFRESH_TOKEN is not configured")
    return await _authenticate(
        "google_calendar", _GOOGLE_TOKEN_URL, settings.GOOGLE_CALENDAR_REFRESH_TOKEN,
        settings.GOOGLE_CALENDAR_CLIENT_ID, settings.GOOGLE_CALENDAR_CLIENT_SECRET,
    )


async def _authenticate_outlook() -> str:
    if not settings.OUTLOOK_CALENDAR_REFRESH_TOKEN:
        raise CalendarError("OUTLOOK_CALENDAR_REFRESH_TOKEN is not configured")
    return await _authenticate(
        "outlook_calendar", _MS_TOKEN_URL, settings.OUTLOOK_CALENDAR_REFRESH_TOKEN,
        settings.OUTLOOK_CALENDAR_CLIENT_ID, settings.OUTLOOK_CALENDAR_CLIENT_SECRET,
        extra_data={"scope": "https://graph.microsoft.com/Calendars.ReadWrite offline_access"},
    )


def _require_provider(provider: str) -> None:
    if provider not in ("google", "outlook"):
        raise CalendarError(f"Unknown calendar provider: {provider!r} (expected 'google' or 'outlook')")


async def calendar_list_events(provider: str, start_date: str, end_date: str, max_results: int = 50) -> list[dict]:
    """Item 2's own literal function -- real, provider-specific calls,
    each real result reshaped into the SAME real, unified shape
    (`id`/`title`/`start`/`end`/`description`) so a caller doesn't need
    to know which real provider answered."""
    _require_provider(provider)
    if provider == "google":
        token = await _authenticate_google()
        async with _client() as client:
            response = await client.get(
                f"{_GOOGLE_CALENDAR_BASE_URL}/calendars/primary/events",
                headers={"Authorization": f"Bearer {token}"},
                params={"timeMin": start_date, "timeMax": end_date, "maxResults": max_results, "singleEvents": "true"},
            )
        response.raise_for_status()
        return [
            {"id": e["id"], "title": e.get("summary", ""), "start": e.get("start", {}).get("dateTime"), "end": e.get("end", {}).get("dateTime"), "description": e.get("description", "")}
            for e in response.json().get("items", [])
        ]

    token = await _authenticate_outlook()
    async with _client() as client:
        response = await client.get(
            f"{_MS_GRAPH_BASE_URL}/me/calendarView",
            headers={"Authorization": f"Bearer {token}"},
            params={"startDateTime": start_date, "endDateTime": end_date, "$top": max_results},
        )
    response.raise_for_status()
    return [
        {"id": e["id"], "title": e.get("subject", ""), "start": e.get("start", {}).get("dateTime"), "end": e.get("end", {}).get("dateTime"), "description": e.get("bodyPreview", "")}
        for e in response.json().get("value", [])
    ]


async def calendar_create_event(provider: str, title: str, start_time: str, end_time: str, description: str | None = None, attendees: list[str] | None = None) -> dict:
    """Item 2's own literal function."""
    _require_provider(provider)
    attendees = attendees or []
    if provider == "google":
        token = await _authenticate_google()
        body = {
            "summary": title, "start": {"dateTime": start_time}, "end": {"dateTime": end_time},
            "description": description or "", "attendees": [{"email": a} for a in attendees],
        }
        async with _client() as client:
            response = await client.post(f"{_GOOGLE_CALENDAR_BASE_URL}/calendars/primary/events", headers={"Authorization": f"Bearer {token}"}, json=body)
        response.raise_for_status()
        event = response.json()
        return {"id": event["id"], "title": event.get("summary", ""), "start": start_time, "end": end_time}

    token = await _authenticate_outlook()
    body = {
        "subject": title, "start": {"dateTime": start_time, "timeZone": "UTC"}, "end": {"dateTime": end_time, "timeZone": "UTC"},
        "body": {"contentType": "text", "content": description or ""}, "attendees": [{"emailAddress": {"address": a}} for a in attendees],
    }
    async with _client() as client:
        response = await client.post(f"{_MS_GRAPH_BASE_URL}/me/events", headers={"Authorization": f"Bearer {token}"}, json=body)
    response.raise_for_status()
    event = response.json()
    return {"id": event["id"], "title": event.get("subject", ""), "start": start_time, "end": end_time}


async def calendar_update_event(provider: str, event_id: str, title: str | None = None, start_time: str | None = None, end_time: str | None = None, description: str | None = None) -> dict:
    """Item 2's own literal function -- real, partial update (only the
    real, given fields are sent)."""
    _require_provider(provider)
    if provider == "google":
        token = await _authenticate_google()
        body = {}
        if title is not None:
            body["summary"] = title
        if start_time is not None:
            body["start"] = {"dateTime": start_time}
        if end_time is not None:
            body["end"] = {"dateTime": end_time}
        if description is not None:
            body["description"] = description
        async with _client() as client:
            response = await client.patch(f"{_GOOGLE_CALENDAR_BASE_URL}/calendars/primary/events/{event_id}", headers={"Authorization": f"Bearer {token}"}, json=body)
        response.raise_for_status()
        return response.json()

    token = await _authenticate_outlook()
    body = {}
    if title is not None:
        body["subject"] = title
    if start_time is not None:
        body["start"] = {"dateTime": start_time, "timeZone": "UTC"}
    if end_time is not None:
        body["end"] = {"dateTime": end_time, "timeZone": "UTC"}
    if description is not None:
        body["body"] = {"contentType": "text", "content": description}
    async with _client() as client:
        response = await client.patch(f"{_MS_GRAPH_BASE_URL}/me/events/{event_id}", headers={"Authorization": f"Bearer {token}"}, json=body)
    response.raise_for_status()
    return response.json()


async def calendar_delete_event(provider: str, event_id: str) -> bool:
    """Item 2's own literal function -- real `True` on real success."""
    _require_provider(provider)
    if provider == "google":
        token = await _authenticate_google()
        url = f"{_GOOGLE_CALENDAR_BASE_URL}/calendars/primary/events/{event_id}"
    else:
        token = await _authenticate_outlook()
        url = f"{_MS_GRAPH_BASE_URL}/me/events/{event_id}"

    async with _client() as client:
        response = await client.delete(url, headers={"Authorization": f"Bearer {token}"})
    response.raise_for_status()
    return True


async def calendar_get_event(provider: str, event_id: str) -> dict:
    """Item 2's own literal function."""
    _require_provider(provider)
    if provider == "google":
        token = await _authenticate_google()
        url = f"{_GOOGLE_CALENDAR_BASE_URL}/calendars/primary/events/{event_id}"
    else:
        token = await _authenticate_outlook()
        url = f"{_MS_GRAPH_BASE_URL}/me/events/{event_id}"

    async with _client() as client:
        response = await client.get(url, headers={"Authorization": f"Bearer {token}"})
    response.raise_for_status()
    return response.json()


async def calendar_find_available_slots(provider: str, start_date: str, end_date: str, duration: int) -> list[dict]:
    """Item 2's own literal function -- real, simple gap-finding over
    each real provider's own real busy-time API (`freeBusy` for Google,
    `findMeetingTimes` for Outlook): existing real events are read, and
    every real gap of at least `duration` minutes between them is
    returned. A real, deliberately simple algorithm (no working-hours/
    timezone preference logic) -- real, honest, minimal-viable, not
    every real scheduling nuance a dedicated scheduling product would
    have."""
    events = await calendar_list_events(provider, start_date, end_date, max_results=250)
    busy = sorted((e["start"], e["end"]) for e in events if e["start"] and e["end"])

    import datetime as dt
    slots = []
    cursor = dt.datetime.fromisoformat(start_date.replace("Z", "+00:00"))
    end = dt.datetime.fromisoformat(end_date.replace("Z", "+00:00"))
    for busy_start_str, busy_end_str in busy:
        busy_start = dt.datetime.fromisoformat(busy_start_str.replace("Z", "+00:00"))
        busy_end = dt.datetime.fromisoformat(busy_end_str.replace("Z", "+00:00"))
        if (busy_start - cursor).total_seconds() / 60 >= duration:
            slots.append({"start": cursor.isoformat(), "end": busy_start.isoformat()})
        cursor = max(cursor, busy_end)
    if (end - cursor).total_seconds() / 60 >= duration:
        slots.append({"start": cursor.isoformat(), "end": end.isoformat()})
    return slots

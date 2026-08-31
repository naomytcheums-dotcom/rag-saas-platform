"""
Phase 02: real external integrations with real side effects, gated behind a
Google service account the user provisions themselves (see README's "Phase
02 setup" section -- a Google Cloud project, Calendar API + Sheets API
enabled, a service account key, and the target calendar/sheet shared with
that service account's email).

Two integrations:

- CalendarClient.book_escalation -- books a real Google Calendar event
  when the agent can't resolve a question from the docs or GitHub and a
  human needs to step in.
- SheetsClient.log_question -- appends a real row to a tracking sheet for
  every question the agent judges notable (unanswered, or a likely
  documentation gap), so a human can spot patterns later.

Both classes accept an injectable `service` object -- the same pattern
agent.py's search_github_issues() uses for its http_client -- so the
request-shaping logic (what gets sent, how errors surface) is fully
testable without real Google credentials. What is NOT tested anywhere in
this codebase yet is a live call against a real account; that's this
phase's version of the Anthropic-credit blocker on generation.py.
"""

import datetime as dt
import os

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/spreadsheets",
]

DEFAULT_EVENT_DURATION_MINUTES = 30
DEFAULT_TIMEZONE = "UTC"
DEFAULT_SHEET_RANGE = "Sheet1!A1"


def _load_credentials():
    key_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")
    if not key_path:
        raise EnvironmentError(
            "GOOGLE_SERVICE_ACCOUNT_FILE is not set -- point it at a service account "
            "JSON key with the Calendar and Sheets APIs enabled. See README's "
            "'Phase 02 setup' section."
        )
    if not os.path.exists(key_path):
        raise EnvironmentError(f"GOOGLE_SERVICE_ACCOUNT_FILE points to a file that doesn't exist: {key_path}")
    return service_account.Credentials.from_service_account_file(key_path, scopes=SCOPES)


def _raise_for_http_error(exc, api_name):
    raise RuntimeError(f"Google {api_name} API returned an error (status {exc.resp.status}): {exc.reason}") from exc


class CalendarClient:
    def __init__(self, service=None, calendar_id=None):
        self.calendar_id = calendar_id or os.environ.get("GOOGLE_CALENDAR_ID")
        if service is not None:
            self.service = service
        else:
            if not self.calendar_id:
                raise EnvironmentError("GOOGLE_CALENDAR_ID is not set -- which calendar should Nova book on?")
            self.service = build("calendar", "v3", credentials=_load_credentials())

    def book_escalation(self, reason, start_time, duration_minutes=DEFAULT_EVENT_DURATION_MINUTES, timezone=DEFAULT_TIMEZONE):
        """`start_time` is a timezone-aware datetime.datetime. Returns the
        created event's id and a link a human can click to see it."""
        end_time = start_time + dt.timedelta(minutes=duration_minutes)
        event_body = {
            "summary": f"Nova escalation: {reason[:80]}",
            "description": reason,
            "start": {"dateTime": start_time.isoformat(), "timeZone": timezone},
            "end": {"dateTime": end_time.isoformat(), "timeZone": timezone},
        }
        try:
            created = self.service.events().insert(calendarId=self.calendar_id, body=event_body).execute()
        except HttpError as exc:
            _raise_for_http_error(exc, "Calendar")
        return {
            "event_id": created.get("id"),
            "link": created.get("htmlLink"),
            "start": event_body["start"]["dateTime"],
        }


class SheetsClient:
    def __init__(self, service=None, sheet_id=None, sheet_range=DEFAULT_SHEET_RANGE):
        self.sheet_id = sheet_id or os.environ.get("GOOGLE_SHEET_ID")
        self.sheet_range = sheet_range
        if service is not None:
            self.service = service
        else:
            if not self.sheet_id:
                raise EnvironmentError("GOOGLE_SHEET_ID is not set -- which spreadsheet should Nova log to?")
            self.service = build("sheets", "v4", credentials=_load_credentials())

    def log_question(self, question, category, answered):
        row = [dt.datetime.now(dt.timezone.utc).isoformat(), question, category, "yes" if answered else "no"]
        try:
            self.service.spreadsheets().values().append(
                spreadsheetId=self.sheet_id,
                range=self.sheet_range,
                valueInputOption="RAW",
                body={"values": [row]},
            ).execute()
        except HttpError as exc:
            _raise_for_http_error(exc, "Sheets")
        return {"logged": True, "row": row}

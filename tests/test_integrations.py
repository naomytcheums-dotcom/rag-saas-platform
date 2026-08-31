"""
Unit tests for src/integrations.py.

Same approach as test_agent.py's GitHub tool tests: real request-shaping
and error-handling logic, exercised against fake stand-ins for the
Google API client's chained service objects -- no real credentials, no
live network call. A live call against a real calendar/sheet is this
phase's untested-by-design gap, same as generation.py's Anthropic-credit
blocker -- see README.
"""

import datetime as dt
import json
import sys
from pathlib import Path

import pytest
from googleapiclient.errors import HttpError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from integrations import CalendarClient, SheetsClient  # noqa: E402


class FakeHttpResp:
    def __init__(self, status, reason="Error"):
        self.status = status
        self.reason = reason


def make_http_error(status=500, reason="Internal Server Error", message="boom"):
    content = json.dumps({"error": {"message": message}}).encode("utf-8")
    return HttpError(FakeHttpResp(status, reason), content)


# ---- fake Calendar service (mimics googleapiclient's chained calls) ------

class FakeCalendarService:
    def __init__(self, insert_result=None, exc=None):
        self._insert_result = insert_result if insert_result is not None else {}
        self._exc = exc
        self.insert_calls = []

    def events(self):
        return self

    def insert(self, calendarId, body):
        self.insert_calls.append({"calendarId": calendarId, "body": body})
        return self

    def execute(self):
        if self._exc is not None:
            raise self._exc
        return self._insert_result


# ---- fake Sheets service --------------------------------------------------

class FakeSheetsService:
    def __init__(self, exc=None):
        self._exc = exc
        self.append_calls = []

    def spreadsheets(self):
        return self

    def values(self):
        return self

    def append(self, spreadsheetId, range, valueInputOption, body):
        self.append_calls.append(
            {"spreadsheetId": spreadsheetId, "range": range, "valueInputOption": valueInputOption, "body": body}
        )
        return self

    def execute(self):
        if self._exc is not None:
            raise self._exc
        return {}


# ---- CalendarClient --------------------------------------------------------

def test_book_escalation_sends_the_reason_and_a_30min_window_by_default():
    fake = FakeCalendarService(insert_result={"id": "evt_1", "htmlLink": "https://calendar.google.com/evt_1"})
    client = CalendarClient(service=fake, calendar_id="team@example.com")
    start = dt.datetime(2026, 8, 20, 15, 0, tzinfo=dt.timezone.utc)

    result = client.book_escalation("User needs help with a WebSocket auth edge case", start)

    call = fake.insert_calls[0]
    assert call["calendarId"] == "team@example.com"
    body = call["body"]
    assert body["start"]["dateTime"] == "2026-08-20T15:00:00+00:00"
    assert body["end"]["dateTime"] == "2026-08-20T15:30:00+00:00"
    assert "WebSocket auth edge case" in body["description"]
    assert result == {"event_id": "evt_1", "link": "https://calendar.google.com/evt_1", "start": "2026-08-20T15:00:00+00:00"}


def test_book_escalation_truncates_a_long_reason_in_the_summary_only():
    fake = FakeCalendarService(insert_result={"id": "evt_2", "htmlLink": "u"})
    client = CalendarClient(service=fake, calendar_id="team@example.com")
    long_reason = "x" * 200

    client.book_escalation(long_reason, dt.datetime(2026, 8, 20, 15, 0, tzinfo=dt.timezone.utc))

    body = fake.insert_calls[0]["body"]
    assert len(body["summary"]) <= len("Nova escalation: ") + 80
    assert body["description"] == long_reason  # full reason kept, only the summary is trimmed


def test_book_escalation_wraps_an_http_error_with_the_status_code():
    fake = FakeCalendarService(exc=make_http_error(status=403, message="Calendar not shared with this account"))
    client = CalendarClient(service=fake, calendar_id="team@example.com")

    with pytest.raises(RuntimeError, match="status 403"):
        client.book_escalation("anything", dt.datetime(2026, 8, 20, 15, 0, tzinfo=dt.timezone.utc))


def test_calendar_client_refuses_to_build_a_real_service_without_a_calendar_id(monkeypatch):
    monkeypatch.delenv("GOOGLE_CALENDAR_ID", raising=False)
    with pytest.raises(EnvironmentError, match="GOOGLE_CALENDAR_ID"):
        CalendarClient(service=None)


# ---- SheetsClient -----------------------------------------------------------

def test_log_question_appends_a_row_with_timestamp_question_category_and_answered_flag():
    fake = FakeSheetsService()
    client = SheetsClient(service=fake, sheet_id="sheet_1")

    result = client.log_question("Does FastAPI support server-sent events?", "feature-gap", answered=False)

    call = fake.append_calls[0]
    assert call["spreadsheetId"] == "sheet_1"
    row = call["body"]["values"][0]
    assert row[1] == "Does FastAPI support server-sent events?"
    assert row[2] == "feature-gap"
    assert row[3] == "no"
    assert result["logged"] is True


def test_log_question_marks_answered_true_as_yes():
    fake = FakeSheetsService()
    SheetsClient(service=fake, sheet_id="sheet_1").log_question("q", "usage", answered=True)
    assert fake.append_calls[0]["body"]["values"][0][3] == "yes"


def test_log_question_wraps_an_http_error_with_the_status_code():
    fake = FakeSheetsService(exc=make_http_error(status=404, message="Sheet not found"))
    client = SheetsClient(service=fake, sheet_id="sheet_1")

    with pytest.raises(RuntimeError, match="status 404"):
        client.log_question("q", "usage", answered=True)


def test_sheets_client_refuses_to_build_a_real_service_without_a_sheet_id(monkeypatch):
    monkeypatch.delenv("GOOGLE_SHEET_ID", raising=False)
    with pytest.raises(EnvironmentError, match="GOOGLE_SHEET_ID"):
        SheetsClient(service=None)

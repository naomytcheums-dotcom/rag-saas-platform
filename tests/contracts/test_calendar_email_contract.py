"""Specs 5.2.7 calendar (Google, Outlook), 5.2.8 e-mail (Gmail, Outlook), 5.4.11 calendar workflow block -- CONTRACT tests against LOCAL FAKE servers
that speak the Google OAuth / Google Calendar / Gmail and Microsoft identity / Graph protocols. The product code (api/tools/*.py, oauth_api.py) is real
and runs over a real loopback socket; the vendors are fake. Real validation: scripts/validate_google_microsoft_live.py."""

import base64
import email
import json
from email import policy

import pytest

from api.config import settings
from api.tools import calendar_tools, email_tools
from vendor_fakes import FakeVendor, Resp, closed_url


@pytest.fixture(autouse=True)
def _credentials(monkeypatch):
    for name, value in {
        "GOOGLE_CALENDAR_REFRESH_TOKEN": "g-refresh", "GOOGLE_CALENDAR_CLIENT_ID": "g-client", "GOOGLE_CALENDAR_CLIENT_SECRET": "g-secret",
        "OUTLOOK_CALENDAR_REFRESH_TOKEN": "o-refresh", "OUTLOOK_CALENDAR_CLIENT_ID": "o-client", "OUTLOOK_CALENDAR_CLIENT_SECRET": "o-secret",
        "GMAIL_REFRESH_TOKEN": "gm-refresh", "GMAIL_CLIENT_ID": "gm-client", "GMAIL_CLIENT_SECRET": "gm-secret",
        "OUTLOOK_EMAIL_REFRESH_TOKEN": "om-refresh", "OUTLOOK_EMAIL_CLIENT_ID": "om-client", "OUTLOOK_EMAIL_CLIENT_SECRET": "om-secret",
    }.items():
        monkeypatch.setattr(settings, name, value)
    calendar_tools._access_token_cache.clear()
    email_tools._access_token_cache.clear()

    import asyncio

    real_sleep = asyncio.sleep

    async def fast_sleep(delay):  # Retry-After back-off is not what is under test
        await real_sleep(0)

    monkeypatch.setattr("api.tools.oauth_api.asyncio.sleep", fast_sleep)


@pytest.fixture
def vendor(monkeypatch):
    """One fake that plays the token endpoint of both vendors plus Google Calendar/Gmail (/google) and Graph (/graph)."""
    with FakeVendor() as fake:
        counter = {"n": 0}

        def token(req):
            counter["n"] += 1
            return Resp(200, {"access_token": f"access-{counter['n']}", "expires_in": 3600, "token_type": "Bearer"})

        fake.on("POST", "/token", token)
        for module in (calendar_tools, email_tools):
            monkeypatch.setattr(module, "_GOOGLE_TOKEN_URL" if module is calendar_tools else "_GMAIL_TOKEN_URL", f"{fake.url}/token")
            monkeypatch.setattr(module, "_MS_TOKEN_URL", f"{fake.url}/token")
        monkeypatch.setattr(calendar_tools, "_GOOGLE_CALENDAR_BASE_URL", f"{fake.url}/google/calendar/v3")
        monkeypatch.setattr(calendar_tools, "_MS_GRAPH_BASE_URL", f"{fake.url}/graph/v1.0")
        monkeypatch.setattr(email_tools, "_GMAIL_API_BASE", f"{fake.url}/google/gmail/v1")
        monkeypatch.setattr(email_tools, "_MS_GRAPH_BASE", f"{fake.url}/graph/v1.0")
        fake.token_calls = counter
        yield fake


def api_calls(fake, prefix):
    return [r for r in fake.requests if r.path.startswith(prefix)]


# ----------------------------------------------------------------------------------------------------------------------------- calendar


GOOGLE_EVENTS = {"items": [
    {"id": "g1", "summary": "Standup", "start": {"dateTime": "2026-10-14T09:00:00Z"}, "end": {"dateTime": "2026-10-14T09:30:00Z"}, "description": "daily"},
    {"id": "g2", "summary": "All day", "start": {"date": "2026-10-14"}, "end": {"date": "2026-10-15"}},
]}
GRAPH_EVENTS = {"value": [
    {"id": "o1", "subject": "Review", "start": {"dateTime": "2026-10-14T10:00:00.0000000", "timeZone": "UTC"}, "end": {"dateTime": "2026-10-14T11:00:00.0000000", "timeZone": "UTC"}, "bodyPreview": "q3"},
]}


async def test_google_list_events_request_shape_and_unified_result(vendor):
    vendor.on("GET", "/google/calendar/v3/calendars/primary/events", Resp(200, GOOGLE_EVENTS))
    events = await calendar_tools.calendar_list_events("google", "2026-10-14T00:00:00Z", "2026-10-15T00:00:00Z")
    assert events[0] == {"id": "g1", "title": "Standup", "start": "2026-10-14T09:00:00Z", "end": "2026-10-14T09:30:00Z", "description": "daily"}
    assert events[1]["start"] is None  # an all-day event has `date`, not `dateTime`
    token_request = vendor.calls("POST", "/token")[0]
    assert token_request.form() == {"grant_type": "refresh_token", "refresh_token": "g-refresh", "client_id": "g-client", "client_secret": "g-secret"}
    request = api_calls(vendor, "/google")[0]
    assert request.headers["authorization"] == "Bearer access-1"
    assert request.query["timeMin"] == ["2026-10-14T00:00:00Z"] and request.query["singleEvents"] == ["true"]


async def test_google_list_events_follows_pagination(vendor):
    page1 = {"items": [{"id": "a", "summary": "A", "start": {"dateTime": "2026-10-14T09:00:00Z"}, "end": {"dateTime": "2026-10-14T10:00:00Z"}}], "nextPageToken": "T2"}
    page2 = {"items": [{"id": "b", "summary": "B", "start": {"dateTime": "2026-10-14T11:00:00Z"}, "end": {"dateTime": "2026-10-14T12:00:00Z"}}]}
    vendor.on("GET", "/google/calendar/v3/calendars/primary/events", lambda r: Resp(200, page2 if r.query.get("pageToken") == ["T2"] else page1))
    events = await calendar_tools.calendar_list_events("google", "2026-10-14T00:00:00Z", "2026-10-15T00:00:00Z")
    assert [e["id"] for e in events] == ["a", "b"]


async def test_outlook_list_events_makes_graph_datetimes_explicit_utc_and_slots_work(vendor):
    vendor.on("GET", "/graph/v1.0/me/calendarView", Resp(200, GRAPH_EVENTS))
    events = await calendar_tools.calendar_list_events("outlook", "2026-10-14T08:00:00Z", "2026-10-14T18:00:00Z")
    assert events[0]["start"] == "2026-10-14T10:00:00Z" and events[0]["end"] == "2026-10-14T11:00:00Z"
    # naive Graph datetimes used to be compared with the aware window and raise TypeError in find_available_slots
    slots = await calendar_tools.calendar_find_available_slots("outlook", "2026-10-14T08:00:00Z", "2026-10-14T18:00:00Z", 60)
    assert [(s["start"][:16], s["end"][:16]) for s in slots] == [("2026-10-14T08:00", "2026-10-14T10:00"), ("2026-10-14T11:00", "2026-10-14T18:00")]
    assert vendor.calls("GET", "/graph/v1.0/me/calendarView")[0].headers["authorization"] == "Bearer access-1"


async def test_create_event_bodies_for_both_vendors(vendor):
    vendor.on("POST", "/google/calendar/v3/calendars/primary/events", Resp(200, {"id": "new-g", "summary": "Sync"}))
    vendor.on("POST", "/graph/v1.0/me/events", Resp(201, {"id": "new-o", "subject": "Sync"}))
    g = await calendar_tools.calendar_create_event("google", "Sync", "2026-10-14T09:00:00Z", "2026-10-14T10:00:00Z", "d", ["a@example.com"])
    o = await calendar_tools.calendar_create_event("outlook", "Sync", "2026-10-14T09:00:00", "2026-10-14T10:00:00", "d", ["a@example.com"])
    assert g["id"] == "new-g" and o["id"] == "new-o"
    gb = vendor.calls("POST", "/google/calendar/v3/calendars/primary/events")[0].json()
    assert gb["summary"] == "Sync" and gb["attendees"] == [{"email": "a@example.com"}] and gb["start"] == {"dateTime": "2026-10-14T09:00:00Z"}
    ob = vendor.calls("POST", "/graph/v1.0/me/events")[0].json()
    assert ob["subject"] == "Sync" and ob["attendees"] == [{"emailAddress": {"address": "a@example.com"}}] and ob["start"]["timeZone"] == "UTC"


async def test_update_get_delete_use_the_vendor_methods_and_escape_the_event_id(vendor):
    vendor.on("PATCH", "/google/calendar/v3/calendars/primary/events/*", Resp(200, {"id": "x"}))
    vendor.on("GET", "/google/calendar/v3/calendars/primary/events/*", Resp(200, {"id": "x", "summary": "S"}))
    vendor.on("DELETE", "/google/calendar/v3/calendars/primary/events/*", Resp(204, ""))
    await calendar_tools.calendar_update_event("google", "evt/1?x", title="New")
    assert (await calendar_tools.calendar_get_event("google", "evt/1?x"))["summary"] == "S"
    assert await calendar_tools.calendar_delete_event("google", "evt/1?x") is True
    patch = vendor.calls("PATCH")[0]
    assert patch.path.endswith("/events/evt%2F1%3Fx") and patch.json() == {"summary": "New"}  # only the given field is sent; the id cannot change the route


async def test_access_token_is_cached_and_refreshed_once_on_a_401(vendor):
    answers = [Resp(401, {"error": {"code": 401, "message": "Invalid Credentials", "status": "UNAUTHENTICATED"}}), Resp(200, GOOGLE_EVENTS)]
    vendor.on("GET", "/google/calendar/v3/calendars/primary/events", answers)
    await calendar_tools.calendar_list_events("google", "a", "b")
    assert vendor.token_calls["n"] == 2  # the revoked token was dropped and a new one fetched
    assert [r.headers["authorization"] for r in api_calls(vendor, "/google")] == ["Bearer access-1", "Bearer access-2"]
    await calendar_tools.calendar_list_events("google", "a", "b")
    assert vendor.token_calls["n"] == 2  # and the new one is cached


async def test_a_second_401_is_an_error_not_a_loop(vendor):
    vendor.on("GET", "/google/calendar/v3/calendars/primary/events", Resp(401, {"error": {"code": 401, "message": "Invalid Credentials"}}))
    with pytest.raises(calendar_tools.CalendarError, match="401"):
        await calendar_tools.calendar_list_events("google", "a", "b")
    assert len(api_calls(vendor, "/google")) == 2 and vendor.token_calls["n"] == 2


async def test_revoked_refresh_token_is_a_typed_error_with_the_oauth_code(vendor):
    vendor._routes.clear()
    vendor.on("POST", "/token", Resp(400, {"error": "invalid_grant", "error_description": "Token has been expired or revoked."}))
    with pytest.raises(calendar_tools.CalendarError, match="invalid_grant"):
        await calendar_tools.calendar_list_events("google", "a", "b")
    assert api_calls(vendor, "/google") == []  # no API call without a token


async def test_rate_limit_is_retried_and_5xx_only_for_reads(vendor):
    vendor.on("GET", "/google/calendar/v3/calendars/primary/events", [Resp(429, {"error": {"message": "Rate Limit Exceeded"}}, headers={"retry-after": "0"}), Resp(503, {"error": {"message": "backend"}}), Resp(200, GOOGLE_EVENTS)])
    assert len(await calendar_tools.calendar_list_events("google", "a", "b")) == 2
    assert len(api_calls(vendor, "/google")) == 3
    vendor.on("POST", "/graph/v1.0/me/events", Resp(502, {"error": {"message": "bad gateway"}}))
    with pytest.raises(calendar_tools.CalendarError, match="502"):
        await calendar_tools.calendar_create_event("outlook", "t", "2026-10-14T09:00:00", "2026-10-14T10:00:00")
    assert len(vendor.calls("POST", "/graph/v1.0/me/events")) == 1  # a create is never replayed after a 5xx: it could create the event twice


async def test_forbidden_not_found_and_timeout_are_typed_errors(vendor, monkeypatch):
    vendor.on("GET", "/google/calendar/v3/calendars/primary/events/*", Resp(404, {"error": {"code": 404, "message": "Not Found"}}))
    with pytest.raises(calendar_tools.CalendarError, match="404.*Not Found"):
        await calendar_tools.calendar_get_event("google", "ghost")
    vendor.on("GET", "/graph/v1.0/me/calendarView", Resp(403, {"error": {"code": "ErrorAccessDenied", "message": "Access is denied."}}))
    with pytest.raises(calendar_tools.CalendarError, match="403"):
        await calendar_tools.calendar_list_events("outlook", "a", "b")
    monkeypatch.setattr(calendar_tools, "_TIMEOUT_SECONDS", 0.3)
    vendor.on("GET", "/google/calendar/v3/calendars/primary/events", Resp(200, {}, delay=1.5))
    with pytest.raises(calendar_tools.CalendarError, match="in time"):
        await calendar_tools.calendar_list_events("google", "a", "b")


async def test_provider_down_is_a_typed_error(vendor, monkeypatch):
    monkeypatch.setattr(calendar_tools, "_GOOGLE_CALENDAR_BASE_URL", f"{closed_url()}/calendar/v3")  # nothing listens on the discard port
    with pytest.raises(calendar_tools.CalendarError, match="could not reach"):
        await calendar_tools.calendar_list_events("google", "a", "b")


async def test_workflow_block_turns_a_provider_failure_into_a_block_error_and_a_success_into_output(vendor):
    from api.services.workflow_block_calendar import execute_calendar_block
    from api.services.workflow_blocks import WorkflowBlockError

    config = {"provider": "google", "action": "list", "start_time": "2026-10-14T00:00:00Z", "end_time": "2026-10-15T00:00:00Z", "output_key": "agenda"}
    vendor.on("GET", "/google/calendar/v3/calendars/primary/events", [Resp(500, {"error": {"message": "backend error"}})] * 3 + [Resp(200, GOOGLE_EVENTS)])
    with pytest.raises(WorkflowBlockError, match="calendar block failed.*500"):
        await execute_calendar_block(config, {})
    out = await execute_calendar_block(config, {})  # the vendor recovered
    assert out["agenda"]["results"][0]["title"] == "Standup"


# ----------------------------------------------------------------------------------------------------------------------------- e-mail


def decode_raw(request) -> email.message.EmailMessage:
    return email.message_from_bytes(base64.urlsafe_b64decode(request.json()["raw"]), policy=policy.default)


async def test_gmail_send_is_a_complete_rfc822_message_with_cc_bcc_and_attachment(vendor):
    vendor.on("POST", "/google/gmail/v1/users/me/messages/send", Resp(200, {"id": "sent-1", "threadId": "t1"}))
    result = await email_tools.email_send("gmail", ["to@example.com"], "Hello é", "Body text", cc=["cc@example.com"], bcc=["bcc@example.com"], attachments=[{"filename": "a.bin", "content": b"\x00\x01"}])
    assert result == {"status": "sent", "provider": "gmail", "id": "sent-1"}
    request = vendor.calls("POST", "/google/gmail/v1/users/me/messages/send")[0]
    assert request.headers["authorization"] == "Bearer access-1"
    message = decode_raw(request)
    assert message["To"] == "to@example.com" and message["Cc"] == "cc@example.com" and message["Bcc"] == "bcc@example.com"
    assert message["Subject"] == "Hello é"
    assert message.get_body(("plain",)).get_content().strip() == "Body text"
    assert [part.get_filename() for part in message.iter_attachments()] == ["a.bin"]


async def test_outlook_send_payload(vendor):
    vendor.on("POST", "/graph/v1.0/me/sendMail", Resp(202, ""))
    await email_tools.email_send("outlook", ["to@example.com"], "Hi", "Body", cc=["c@example.com"], bcc=["b@example.com"], attachments=[{"filename": "a.txt", "content": b"hey"}])
    message = vendor.calls("POST", "/graph/v1.0/me/sendMail")[0].json()["message"]
    assert message["toRecipients"] == [{"emailAddress": {"address": "to@example.com"}}]
    assert message["bccRecipients"] == [{"emailAddress": {"address": "b@example.com"}}]
    assert message["attachments"][0]["contentBytes"] == base64.b64encode(b"hey").decode()


GMAIL_ORIGINAL = {"id": "m1", "threadId": "thr-9", "snippet": "Can we meet?", "payload": {"headers": [
    {"name": "Subject", "value": "Meeting"}, {"name": "From", "value": "Alice <alice@example.com>"}, {"name": "Date", "value": "Tue, 13 Oct 2026 09:00:00 +0000"},
    {"name": "Message-ID", "value": "<orig@mail.example.com>"}, {"name": "References", "value": "<older@mail.example.com>"}]}}


def gmail_mailbox(vendor):
    vendor.on("GET", "/google/gmail/v1/users/me/messages", Resp(200, {"messages": [{"id": "m1", "threadId": "thr-9"}], "resultSizeEstimate": 1}))
    vendor.on("GET", "/google/gmail/v1/users/me/messages/m1", lambda r: Resp(200, GMAIL_ORIGINAL))
    vendor.on("POST", "/google/gmail/v1/users/me/messages/send", Resp(200, {"id": "reply-1", "threadId": "thr-9"}))


async def test_gmail_read_returns_subject_sender_date_and_snippet(vendor):
    gmail_mailbox(vendor)
    messages = await email_tools.email_read("gmail", unread_only=True, limit=5)
    assert messages == [{"id": "m1", "subject": "Meeting", "from": "Alice <alice@example.com>", "date": "Tue, 13 Oct 2026 09:00:00 +0000", "snippet": "Can we meet?"}]
    listing = vendor.calls("GET", "/google/gmail/v1/users/me/messages")[0]
    assert listing.query["q"] == ["in:inbox is:unread"] and listing.query["maxResults"] == ["5"]
    detail = vendor.calls("GET", "/google/gmail/v1/users/me/messages/m1")[0]
    assert detail.query["format"] == ["metadata"] and "Subject" in detail.query["metadataHeaders"]


async def test_gmail_search_passes_the_query(vendor):
    gmail_mailbox(vendor)
    found = await email_tools.email_search("gmail", "from:alice invoice")
    assert found[0]["subject"] == "Meeting"
    assert vendor.calls("GET", "/google/gmail/v1/users/me/messages")[0].query["q"] == ["from:alice invoice"]


async def test_gmail_reply_is_addressed_threaded_and_keeps_the_conversation(vendor):
    gmail_mailbox(vendor)
    result = await email_tools.email_reply("gmail", "m1", "Yes, 3pm works")
    assert result["id"] == "reply-1"
    request = vendor.calls("POST", "/google/gmail/v1/users/me/messages/send")[0]
    assert request.json()["threadId"] == "thr-9"
    message = decode_raw(request)
    assert message["To"] == "Alice <alice@example.com>" and message["Subject"] == "Re: Meeting"
    assert message["In-Reply-To"] == "<orig@mail.example.com>" and message["References"] == "<older@mail.example.com> <orig@mail.example.com>"
    assert "Yes, 3pm works" in message.get_content()


async def test_gmail_forward_carries_the_original_message(vendor):
    original_rfc822 = b"From: alice@example.com\r\nTo: me@example.com\r\nSubject: Meeting\r\n\r\nthe original text"
    vendor.on("GET", "/google/gmail/v1/users/me/messages/m1", Resp(200, {"id": "m1", "raw": base64.urlsafe_b64encode(original_rfc822).decode().rstrip("=")}))
    vendor.on("POST", "/google/gmail/v1/users/me/messages/send", Resp(200, {"id": "fwd-1"}))
    await email_tools.email_forward("gmail", "m1", ["new@example.com"], "FYI")
    message = decode_raw(vendor.calls("POST", "/google/gmail/v1/users/me/messages/send")[0])
    assert message["To"] == "new@example.com"
    (attached,) = list(message.iter_attachments())
    assert attached.get_content_type() == "message/rfc822"
    assert "the original text" in attached.get_content().get_content()


async def test_outlook_read_reply_forward_and_attachments(vendor):
    vendor.on("GET", "/graph/v1.0/me/mailFolders/inbox/messages", Resp(200, {"value": [
        {"id": "AAA=", "subject": "Quote", "from": {"emailAddress": {"address": "bob@example.com"}}, "receivedDateTime": "2026-10-13T08:00:00Z", "bodyPreview": "see attached"}]}))
    vendor.on("POST", "/graph/v1.0/me/messages/*", Resp(202, ""))
    vendor.on("GET", "/graph/v1.0/me/messages/*", Resp(200, {"value": [{"name": "q.pdf", "contentType": "application/pdf"}]}))
    assert (await email_tools.email_read("outlook", unread_only=True))[0] == {
        "id": "AAA=", "subject": "Quote", "from": "bob@example.com", "date": "2026-10-13T08:00:00Z", "snippet": "see attached"}
    assert vendor.calls("GET", "/graph/v1.0/me/mailFolders/inbox/messages")[0].query["$filter"] == ["isRead eq false"]
    await email_tools.email_reply("outlook", "AAA=", "ok")
    await email_tools.email_forward("outlook", "AAA=", ["x@example.com"], "fyi")
    assert await email_tools.email_get_attachments("outlook", "AAA=") == [{"filename": "q.pdf", "content_type": "application/pdf"}]
    paths = [r.path for r in vendor.requests if r.method == "POST" and r.path != "/token"]
    assert paths == ["/graph/v1.0/me/messages/AAA=/reply", "/graph/v1.0/me/messages/AAA=/forward"]


async def test_email_errors_are_typed_and_a_send_is_never_replayed_after_a_5xx(vendor):
    vendor.on("POST", "/google/gmail/v1/users/me/messages/send", Resp(503, {"error": {"code": 503, "message": "The service is currently unavailable."}}))
    with pytest.raises(email_tools.EmailToolError, match="503"):
        await email_tools.email_send("gmail", ["a@example.com"], "s", "b")
    assert len(vendor.calls("POST", "/google/gmail/v1/users/me/messages/send")) == 1  # a second POST could deliver the message twice
    vendor.on("POST", "/graph/v1.0/me/sendMail", [Resp(429, {"error": {"message": "throttled"}}, headers={"retry-after": "0"}), Resp(202, "")])
    assert (await email_tools.email_send("outlook", ["a@example.com"], "s", "b"))["status"] == "sent"
    assert len(vendor.calls("POST", "/graph/v1.0/me/sendMail")) == 2  # 429: the vendor says nothing was processed, so it is retried
    vendor.on("GET", "/google/gmail/v1/users/me/messages", Resp(403, {"error": {"code": 403, "message": "Request had insufficient authentication scopes."}}))
    with pytest.raises(email_tools.EmailToolError, match="insufficient authentication scopes"):
        await email_tools.email_read("gmail")


async def test_email_token_revoked_midway_is_refreshed_once(vendor):
    vendor.on("POST", "/graph/v1.0/me/sendMail", [Resp(401, {"error": {"code": "InvalidAuthenticationToken", "message": "Access token has expired."}}), Resp(202, "")])
    await email_tools.email_send("outlook", ["a@example.com"], "s", "b")
    assert vendor.token_calls["n"] == 2
    token_form = vendor.calls("POST", "/token")[0].form()
    assert token_form["grant_type"] == "refresh_token" and "Mail.Send" in token_form["scope"]


async def test_workflow_email_block_turns_a_provider_failure_into_a_block_error(vendor):
    from api.services.workflow_block_email import execute_email_block
    from api.services.workflow_blocks import WorkflowBlockError

    vendor.on("POST", "/google/gmail/v1/users/me/messages/send", [Resp(500, {"error": {"message": "boom"}}), Resp(200, {"id": "ok-1"})])
    config = {"provider": "gmail", "to": ["{{user.email}}"], "subject": "Hi {{user.name}}", "body": "Body", "output_key": "mail"}
    context = {"user": {"email": "u@example.com", "name": "Uma"}}
    with pytest.raises(WorkflowBlockError, match="email block failed.*500"):
        await execute_email_block(config, context)
    assert decode_raw(vendor.calls("POST", "/google/gmail/v1/users/me/messages/send")[0])["Subject"] == "Hi Uma"
    assert (await execute_email_block(config, context))["mail"]["id"] == "ok-1"

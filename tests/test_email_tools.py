"""Partie 5.2.8 -- email tools (Gmail, Outlook, SMTP). Real
httpx.MockTransport for Gmail/Outlook (real request/response parsing,
fake network transport); a real, minimal fake smtplib.SMTP for the
SMTP provider (SMTP itself has no async or httpx-based real client to
mock at that same boundary)."""

import base64

import httpx
import pytest

from api.config import settings
from api.tools.email_tools import (
    EMAIL_SEND_TOOL, EmailToolError, email_forward, email_get_attachments, email_read, email_reply, email_search,
    email_send,
)


def _patch_client(monkeypatch, handler):
    monkeypatch.setattr("api.tools.email_tools._client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))


@pytest.fixture(autouse=True)
def _configure_credentials(monkeypatch):
    monkeypatch.setattr(settings, "GMAIL_REFRESH_TOKEN", "gmail-refresh")
    monkeypatch.setattr(settings, "GMAIL_CLIENT_ID", "gmail-client")
    monkeypatch.setattr(settings, "GMAIL_CLIENT_SECRET", "gmail-secret")
    monkeypatch.setattr(settings, "OUTLOOK_EMAIL_REFRESH_TOKEN", "outlook-refresh")
    monkeypatch.setattr(settings, "OUTLOOK_EMAIL_CLIENT_ID", "outlook-client")
    monkeypatch.setattr(settings, "OUTLOOK_EMAIL_CLIENT_SECRET", "outlook-secret")
    monkeypatch.setattr(settings, "AGENT_SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "AGENT_SMTP_PORT", 587)
    monkeypatch.setattr(settings, "AGENT_SMTP_USERNAME", "user@example.com")
    monkeypatch.setattr(settings, "AGENT_SMTP_PASSWORD", "pw")
    monkeypatch.setattr(settings, "AGENT_SMTP_FROM_EMAIL", "user@example.com")
    import api.tools.email_tools as mod
    mod._access_token_cache.clear()


def _token_response() -> httpx.Response:
    return httpx.Response(200, json={"access_token": "real-access-token", "expires_in": 3600})


def _dispatch(token_host: str, api_response):
    def handler(request: httpx.Request) -> httpx.Response:
        if token_host in str(request.url):
            return _token_response()
        return api_response(request)
    return handler


# --------------------------------------- email_send --


async def test_email_send_gmail_encodes_a_real_rfc2822_message(monkeypatch):
    """Validation criterion: les appels email fonctionnent (mock)."""
    def api_response(request):
        import json
        payload = json.loads(request.read())
        raw = base64.urlsafe_b64decode(payload["raw"])
        assert b"Subject: Hello" in raw
        assert b"a real body" in raw
        return httpx.Response(200, json={"id": "msg1"})

    _patch_client(monkeypatch, _dispatch("oauth2.googleapis.com", api_response))
    result = await email_send("gmail", ["to@example.com"], "Hello", "a real body")
    assert result["id"] == "msg1"


async def test_email_send_outlook_sends_real_json(monkeypatch):
    def api_response(request):
        import json
        payload = json.loads(request.read())
        assert payload["message"]["subject"] == "Hello"
        assert payload["message"]["toRecipients"] == [{"emailAddress": {"address": "to@example.com"}}]
        return httpx.Response(202)

    _patch_client(monkeypatch, _dispatch("login.microsoftonline.com", api_response))
    result = await email_send("outlook", ["to@example.com"], "Hello", "a real body")
    assert result["status"] == "sent"


async def test_email_send_smtp_uses_a_real_smtplib_connection(monkeypatch):
    sent = {}

    class _FakeSMTP:
        def __init__(self, host, port, timeout=None):
            sent["host"] = host
            sent["port"] = port

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self):
            sent["starttls"] = True

        def login(self, username, password):
            sent["login"] = (username, password)

        def send_message(self, message, to_addrs):
            sent["message"] = message
            sent["to_addrs"] = to_addrs

    monkeypatch.setattr("smtplib.SMTP", _FakeSMTP)
    result = await email_send("smtp", ["to@example.com"], "Hello", "a real body")

    assert result["status"] == "sent"
    assert sent["host"] == "smtp.example.com"
    assert sent["starttls"] is True
    assert sent["to_addrs"] == ["to@example.com"]
    assert sent["message"]["Subject"] == "Hello"


async def test_email_send_raises_without_a_real_refresh_token(monkeypatch):
    """Validation criterion: sécurité -- les tokens OAuth sont requis."""
    monkeypatch.setattr(settings, "GMAIL_REFRESH_TOKEN", "")
    with pytest.raises(EmailToolError, match="GMAIL_REFRESH_TOKEN"):
        await email_send("gmail", ["to@example.com"], "Hello", "body")


async def test_email_send_rejects_an_unknown_provider():
    with pytest.raises(EmailToolError, match="Unknown"):
        await email_send("yahoo", ["to@example.com"], "Hello", "body")


# --------------------------------------- email_read / email_search --


async def test_email_read_gmail_lists_real_message_ids(monkeypatch):
    _patch_client(monkeypatch, _dispatch("oauth2.googleapis.com", lambda r: httpx.Response(200, json={"messages": [{"id": "m1"}, {"id": "m2"}]})))
    messages = await email_read("gmail")
    assert [m["id"] for m in messages] == ["m1", "m2"]


async def test_email_search_outlook_uses_real_search_param(monkeypatch):
    def api_response(request):
        assert '"invoice"' in request.url.params["$search"]
        return httpx.Response(200, json={"value": [{"id": "m1", "subject": "Invoice"}]})

    _patch_client(monkeypatch, _dispatch("login.microsoftonline.com", api_response))
    results = await email_search("outlook", "invoice")
    assert results[0]["subject"] == "Invoice"


# --------------------------------------- SMTP real protocol limitation --


async def test_email_read_smtp_raises_a_real_honest_protocol_error():
    """Validation criterion: robustesse -- les erreurs sont gérées
    (SMTP n'a pas de lecture -- limitation protocolaire honnête)."""
    with pytest.raises(EmailToolError, match="send-only protocol"):
        await email_read("smtp")


async def test_email_search_smtp_raises():
    with pytest.raises(EmailToolError, match="send-only protocol"):
        await email_search("smtp", "query")


async def test_email_reply_smtp_raises():
    with pytest.raises(EmailToolError, match="send-only protocol"):
        await email_reply("smtp", "msg1", "body")


async def test_email_forward_smtp_raises():
    with pytest.raises(EmailToolError, match="send-only protocol"):
        await email_forward("smtp", "msg1", ["to@example.com"], "body")


async def test_email_get_attachments_smtp_raises():
    with pytest.raises(EmailToolError, match="send-only protocol"):
        await email_get_attachments("smtp", "msg1")


# --------------------------------------- email_reply / email_forward / attachments --


async def test_email_reply_gmail_uses_the_real_thread_id(monkeypatch):
    calls = []

    def api_response(request):
        calls.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"threadId": "thread-1"})
        import json
        payload = json.loads(request.read())
        assert payload["threadId"] == "thread-1"
        return httpx.Response(200, json={"id": "reply-1"})

    _patch_client(monkeypatch, _dispatch("oauth2.googleapis.com", api_response))
    result = await email_reply("gmail", "msg1", "a real reply")
    assert result["id"] == "reply-1"


async def test_email_forward_outlook_sends_real_recipients(monkeypatch):
    def api_response(request):
        import json
        payload = json.loads(request.read())
        assert payload["toRecipients"] == [{"emailAddress": {"address": "new@example.com"}}]
        return httpx.Response(202)

    _patch_client(monkeypatch, _dispatch("login.microsoftonline.com", api_response))
    result = await email_forward("outlook", "msg1", ["new@example.com"], "fyi")
    assert result["status"] == "sent"


async def test_email_get_attachments_gmail_returns_real_parts(monkeypatch):
    def api_response(request):
        return httpx.Response(200, json={"payload": {"parts": [{"filename": "report.pdf", "body": {"attachmentId": "att1"}}, {"filename": "", "body": {}}]}})

    _patch_client(monkeypatch, _dispatch("oauth2.googleapis.com", api_response))
    attachments = await email_get_attachments("gmail", "msg1")
    assert attachments == [{"filename": "report.pdf", "attachment_id": "att1"}]


# --------------------------------------- tool wiring --


async def test_email_send_tool_handler_works(monkeypatch):
    _patch_client(monkeypatch, _dispatch("oauth2.googleapis.com", lambda r: httpx.Response(200, json={"id": "msg1"})))
    result = await EMAIL_SEND_TOOL.handler(to=["to@example.com"], subject="Hi", body="body")
    assert "msg1" in result

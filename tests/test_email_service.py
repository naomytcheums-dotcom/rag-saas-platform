"""
Unit tests for api/services/email.py's _send() -- the single low-level
function every send_*_email in that module delegates to. Every other test
file mocks send_*_email itself at the router/service boundary (see
test_auth_api.py's comment on that), so none of them actually exercise
_send()'s real behavior. This file is the one place that does, using a
fake httpx.post instead of a live Resend call.
"""

import httpx
import pytest

from api.config import settings
from api.services import email as email_service


class _FakeResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("POST", email_service.RESEND_API_URL)
            response = httpx.Response(self.status_code, request=request, text="boom")
            raise httpx.HTTPStatusError("error", request=request, response=response)


def test_send_appends_the_support_email_footer_to_every_email(monkeypatch):
    """RGPD Art. 12: this footer is what makes every single outgoing
    email carry a real way to reach the controller -- not just the
    handful of emails someone remembered to add a contact line to by
    hand. Proven here by inspecting the actual payload sent to Resend."""
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured.update(url=url, headers=headers, json=json, timeout=timeout)
        return _FakeResponse(200)

    monkeypatch.setattr(email_service.httpx, "post", fake_post)

    email_service._send("someone@example.com", "Test subject", "<p>Original body</p>")

    assert "<p>Original body</p>" in captured["json"]["html"]
    assert settings.SUPPORT_EMAIL in captured["json"]["html"]
    assert f"mailto:{settings.SUPPORT_EMAIL}" in captured["json"]["html"]


def test_send_footer_is_appended_after_the_original_body(monkeypatch):
    """Order matters for readability -- the footer must read as a
    trailing contact line, not get mixed into or precede the actual
    message."""
    captured = {}
    monkeypatch.setattr(
        email_service.httpx, "post", lambda url, headers, json, timeout: captured.update(json=json) or _FakeResponse(200)
    )

    email_service._send("someone@example.com", "Test subject", "<p>MARKER_BODY</p>")

    html = captured["json"]["html"]
    assert html.index("MARKER_BODY") < html.index(settings.SUPPORT_EMAIL)


def test_send_raises_if_resend_api_key_is_not_set(monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", None)
    with pytest.raises(EnvironmentError, match="RESEND_API_KEY"):
        email_service._send("someone@example.com", "subject", "<p>body</p>")


def test_send_wraps_an_http_error_from_resend(monkeypatch):
    monkeypatch.setattr(
        email_service.httpx, "post", lambda url, headers, json, timeout: _FakeResponse(500)
    )
    with pytest.raises(RuntimeError, match="status 500"):
        email_service._send("someone@example.com", "subject", "<p>body</p>")


def test_send_wraps_a_timeout_from_resend(monkeypatch):
    def raise_timeout(url, headers, json, timeout):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(email_service.httpx, "post", raise_timeout)
    with pytest.raises(RuntimeError, match="timed out"):
        email_service._send("someone@example.com", "subject", "<p>body</p>")


def test_send_wraps_a_network_error_from_resend(monkeypatch):
    def raise_request_error(url, headers, json, timeout):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(email_service.httpx, "post", raise_request_error)
    with pytest.raises(RuntimeError, match="Could not reach Resend"):
        email_service._send("someone@example.com", "subject", "<p>body</p>")

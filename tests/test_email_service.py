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


# Coverage audit finding: every send_*_email function is monkeypatched
# away at its call site by every other test in this project (see this
# module's own docstring) -- meaning none of their actual bodies had
# EVER run for real. A typo referencing an undefined variable or the
# wrong settings attribute inside any one of these would have gone
# completely undetected until real production traffic hit it. This
# calls each one for real, against a mocked httpx.post, proving the
# subject/HTML actually build without error and reach _send() with the
# right recipient.
_ALL_SEND_FUNCTIONS = [
    (email_service.send_password_reset_email, ("someone@example.com", "https://app.example.com/reset?token=abc")),
    (email_service.send_verification_code_email, ("someone@example.com", "123456")),
    (email_service.send_account_restore_email, ("someone@example.com", "https://app.example.com/restore?token=abc")),
    (email_service.send_two_factor_lockout_recovery_requested_email, ("someone@example.com", "https://app.example.com/2fa-recovery?token=abc", 24)),
    (email_service.send_two_factor_lockout_recovery_completed_email, ("someone@example.com",)),
    (email_service.send_new_login_notification_email, ("someone@example.com", "Mozilla/5.0", "203.0.113.5", "2026-01-01T00:00:00Z")),
    (email_service.send_two_factor_enabled_email, ("someone@example.com",)),
    (email_service.send_two_factor_disabled_email, ("someone@example.com",)),
    (email_service.send_recovery_codes_regenerated_email, ("someone@example.com",)),
    (email_service.send_recovery_code_used_email, ("someone@example.com",)),
    (email_service.send_account_deletion_scheduled_email, ("someone@example.com", "2026-06-01T00:00:00Z")),
    (email_service.send_account_deletion_reminder_email, ("someone@example.com", 3)),
    (email_service.send_consent_withdrawn_email, ("someone@example.com",)),
    (email_service.send_consent_reactivation_email, ("someone@example.com", "https://app.example.com/reactivate?token=abc")),
    (email_service.send_password_set_email, ("someone@example.com",)),
    (email_service.send_password_changed_email, ("someone@example.com",)),
    (email_service.send_rate_limit_alert_email, ("someone@example.com", "sign-in")),
]


@pytest.mark.parametrize("send_function,args", _ALL_SEND_FUNCTIONS, ids=lambda v: getattr(v, "__name__", None))
def test_every_send_function_builds_a_valid_request_to_resend(send_function, args, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        email_service.httpx, "post", lambda url, headers, json, timeout: captured.update(json=json) or _FakeResponse(200)
    )

    send_function(*args)

    assert captured["json"]["to"] == ["someone@example.com"]
    assert captured["json"]["subject"]
    assert captured["json"]["html"]
    assert settings.SUPPORT_EMAIL in captured["json"]["html"]  # every email still gets the RGPD Art. 12 footer

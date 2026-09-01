"""Audit finding 21 -- tests for api/services/security_alerts.py."""

from api.config import settings
from api.services import security_alerts


async def test_alert_fires_exactly_at_the_threshold_not_before(client, register_payload, monkeypatch, db_session):
    """A single source IP repeatedly targeting a single email crosses
    BOTH the IP-scoped and email-scoped thresholds on the same request
    -- two distinct, genuinely correct alerts (different information:
    one names the IP, the other the targeted account), not a bug. See
    test_alert_fires_by_ip_independent_of_email below for the case where
    only one of the two dimensions is actually the attack pattern."""
    monkeypatch.setattr(settings, "SECURITY_ALERT_FAILED_LOGIN_THRESHOLD", 3)
    captured_webhook = []
    captured_email = []
    monkeypatch.setattr(security_alerts, "_send_webhook_alert", lambda message: captured_webhook.append(message))
    monkeypatch.setattr(security_alerts, "_send_email_alert", lambda message: captured_email.append(message))

    for _ in range(2):
        await client.post("/auth/login", json={"email": "target@example.com", "password": "wrong"})
    assert captured_webhook == []  # below threshold -- no alert yet

    await client.post("/auth/login", json={"email": "target@example.com", "password": "wrong"})
    assert len(captured_webhook) == 2  # IP-scoped + email-scoped, both crossing at once
    assert any("target@example.com" in message for message in captured_webhook)
    assert any("IP" in message for message in captured_webhook)
    assert captured_email == captured_webhook  # same plain-text messages went to both channels


async def test_alert_does_not_refire_on_every_subsequent_failure_past_the_threshold(client, monkeypatch):
    monkeypatch.setattr(settings, "SECURITY_ALERT_FAILED_LOGIN_THRESHOLD", 2)
    captured = []
    monkeypatch.setattr(security_alerts, "_send_webhook_alert", lambda message: captured.append(message))
    monkeypatch.setattr(security_alerts, "_send_email_alert", lambda message: None)

    for _ in range(5):
        await client.post("/auth/login", json={"email": "target@example.com", "password": "wrong"})

    assert len(captured) == 2  # only the request that crossed the threshold (IP + email), not every one after


async def test_alert_fires_by_ip_independent_of_email(client, monkeypatch):
    """A distributed attack -- many different target emails from ONE IP
    -- must still be caught, even though no single email's count crosses
    the threshold on its own."""
    monkeypatch.setattr(settings, "SECURITY_ALERT_FAILED_LOGIN_THRESHOLD", 3)
    captured = []
    monkeypatch.setattr(security_alerts, "_send_webhook_alert", lambda message: captured.append(message))
    monkeypatch.setattr(security_alerts, "_send_email_alert", lambda message: None)

    for i in range(3):
        await client.post("/auth/login", json={"email": f"victim-{i}@example.com", "password": "wrong"})

    assert len(captured) == 1
    assert "IP" in captured[0]


async def test_no_alert_channels_configured_is_a_silent_no_op(monkeypatch):
    monkeypatch.setattr(settings, "SECURITY_ALERT_WEBHOOK_URL", None)
    monkeypatch.setattr(settings, "SECURITY_ALERT_EMAIL", None)
    # Must not raise, and must not attempt any network/email call.
    security_alerts._send_webhook_alert("test message")
    security_alerts._send_email_alert("test message")


async def test_webhook_failure_does_not_raise(monkeypatch):
    monkeypatch.setattr(settings, "SECURITY_ALERT_WEBHOOK_URL", "http://127.0.0.1:1/nonexistent")
    security_alerts._send_webhook_alert("test message")  # must not raise -- fails open, logs a warning

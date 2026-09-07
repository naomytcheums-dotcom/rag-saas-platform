"""Partie 5.4.10 -- Email workflow block. Real smtplib.SMTP fake, same
precedent as tests/test_email_tools.py's own SMTP test."""

import pytest

from api.config import settings
from api.services.workflow_block_email import (
    execute_email_block, render_email_template, validate_email_config,
)
from api.services.workflow_blocks import WorkflowBlockError


@pytest.fixture(autouse=True)
def _configure_smtp(monkeypatch):
    monkeypatch.setattr(settings, "AGENT_SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "AGENT_SMTP_PORT", 587)
    monkeypatch.setattr(settings, "AGENT_SMTP_USERNAME", "user@example.com")
    monkeypatch.setattr(settings, "AGENT_SMTP_PASSWORD", "pw")
    monkeypatch.setattr(settings, "AGENT_SMTP_FROM_EMAIL", "user@example.com")


class _FakeSMTP:
    sent = {}

    def __init__(self, host, port, timeout=None):
        _FakeSMTP.sent["host"] = host

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def starttls(self):
        pass

    def login(self, username, password):
        pass

    def send_message(self, message, to_addrs):
        _FakeSMTP.sent["message"] = message
        _FakeSMTP.sent["to_addrs"] = to_addrs


@pytest.fixture(autouse=True)
def _patch_smtp(monkeypatch):
    _FakeSMTP.sent = {}
    monkeypatch.setattr("smtplib.SMTP", _FakeSMTP)


# --------------------------------------- validate_email_config / render_email_template --


def test_validate_email_config_accepts_a_real_valid_config():
    validate_email_config({"provider": "smtp", "to": ["a@example.com"], "subject": "Hi", "body": "Hello"})


def test_validate_email_config_rejects_a_missing_field():
    """Validation criterion: la validation fonctionne."""
    with pytest.raises(WorkflowBlockError, match="provider"):
        validate_email_config({"to": ["a@example.com"], "subject": "Hi", "body": "Hello"})


def test_validate_email_config_rejects_a_non_list_to():
    with pytest.raises(WorkflowBlockError):
        validate_email_config({"provider": "smtp", "to": "a@example.com", "subject": "Hi", "body": "Hello"})


def test_render_email_template_substitutes_real_variables():
    """Validation criterion: le rendu des templates fonctionne."""
    assert render_email_template("Hello {{user_name}}", {"user_name": "Ada"}) == "Hello Ada"


def test_render_email_template_substitutes_real_dotted_variables():
    """Validation criterion: item 3's own literal {{user.name}}/{{user.email}}."""
    assert render_email_template("Hello {{user.name}}", {"user": {"name": "Ada"}}) == "Hello Ada"


# --------------------------------------- execute_email_block --


async def test_execute_email_block_sends_a_real_email(monkeypatch):
    """Validation criterion: l'exécution du bloc Email fonctionne."""
    result = await execute_email_block(
        {"provider": "smtp", "to": ["a@example.com"], "subject": "Hi {{name}}", "body": "Hello {{name}}", "output_key": "sent"},
        {"name": "Ada"},
    )
    assert result["sent"]["status"] == "sent"
    assert _FakeSMTP.sent["message"]["Subject"] == "Hi Ada"


async def test_execute_email_block_renders_real_recipient_variables():
    await execute_email_block(
        {"provider": "smtp", "to": ["{{user_email}}"], "subject": "Hi", "body": "Hello"}, {"user_email": "real@example.com"},
    )
    assert _FakeSMTP.sent["to_addrs"] == ["real@example.com"]


async def test_execute_email_block_raises_on_invalid_config():
    """Validation criterion: robustesse -- les erreurs d'envoi sont gérées."""
    with pytest.raises(WorkflowBlockError):
        await execute_email_block({}, {})


async def test_execute_email_block_wraps_a_real_send_failure(monkeypatch):
    monkeypatch.setattr(settings, "AGENT_SMTP_HOST", "")
    with pytest.raises(WorkflowBlockError, match="email block failed"):
        await execute_email_block({"provider": "smtp", "to": ["a@example.com"], "subject": "Hi", "body": "Hello"}, {})

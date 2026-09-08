"""Partie 8.2.13 -- Téléphonie (Twilio)."""

from unittest.mock import AsyncMock, MagicMock, patch

import litellm
import pytest
from litellm.types.utils import Choices, Message, ModelResponse

from api.config import settings
from api.services.telephony import (
    TelephonyError, handle_call_status, handle_dtmf_input, handle_incoming_call, handle_speech_input, list_calls,
    make_outbound_call, verify_twilio_signature,
)


def _real_response(text: str) -> ModelResponse:
    message = Message(content=text, role="assistant")
    choice = Choices(message=message, index=0, finish_reason="stop")
    return ModelResponse(choices=[choice])


@pytest.fixture(autouse=True)
def _configure_key(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")


# ------------------------------------------------------------------- Security


def test_verify_twilio_signature_false_without_auth_token(monkeypatch):
    """Validation criterion: sécurité -- signature vérifiée."""
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", None)
    assert verify_twilio_signature("https://example.com/twilio/incoming", {}, "some-signature") is False


def test_verify_twilio_signature_false_without_signature(monkeypatch):
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "fake-token")
    assert verify_twilio_signature("https://example.com/twilio/incoming", {}, None) is False


def test_verify_twilio_signature_accepts_valid_signature(monkeypatch):
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "fake-token")
    from twilio.request_validator import RequestValidator

    url = "https://example.com/twilio/incoming"
    params = {"CallSid": "CA123", "From": "+15551234567"}
    real_signature = RequestValidator("fake-token").compute_signature(url, params)

    assert verify_twilio_signature(url, params, real_signature) is True


# ------------------------------------------------------------------- Call flow


async def test_handle_incoming_call_creates_record_and_greets(db_session):
    """Validation criterion: les appels entrants fonctionnent."""
    twiml = await handle_incoming_call(db_session, "CA123", "+15551234567", "+15559876543", "agent-1")
    await db_session.commit()

    assert "<Gather" in twiml
    assert "How can I help" in twiml


async def test_handle_speech_input_runs_agent_and_speaks_answer(monkeypatch, db_session):
    """Validation criterion: la saisie vocale est traitée."""
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("Here is your answer.")))
    await handle_incoming_call(db_session, "CA123", "+15551234567", "+15559876543", "agent-1")
    await db_session.commit()

    twiml = await handle_speech_input(db_session, "CA123", "What is RAG?", "agent-1")
    await db_session.commit()

    assert "Here is your answer." in twiml


async def test_handle_dtmf_input_acknowledges_digits(db_session):
    twiml = await handle_dtmf_input(db_session, "CA123", "5")
    await db_session.commit()
    assert "<Gather" in twiml


async def test_handle_call_status_updates_record(db_session):
    """Validation criterion: le statut d'appel est suivi."""
    await handle_incoming_call(db_session, "CA123", "+15551234567", "+15559876543", "agent-1")
    await db_session.commit()

    await handle_call_status(db_session, "CA123", "completed", duration=42)
    await db_session.commit()

    calls = await list_calls(db_session)
    assert calls[0].status == "completed"
    assert calls[0].duration_seconds == 42
    assert calls[0].ended_at is not None


async def test_make_outbound_call_requires_credentials(monkeypatch):
    """Validation criterion: robustesse -- identifiants manquants."""
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", None)
    with pytest.raises(TelephonyError):
        await make_outbound_call("+15551234567", None, "agent-1")


async def test_make_outbound_call_requires_webhook_url(monkeypatch):
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "fake-token")
    monkeypatch.setattr(settings, "TWILIO_WEBHOOK_URL", None)
    with pytest.raises(TelephonyError):
        await make_outbound_call("+15551234567", None, "agent-1")


async def test_make_outbound_call_places_real_call(monkeypatch):
    """Validation criterion: les appels sortants fonctionnent."""
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "fake-token")
    monkeypatch.setattr(settings, "TWILIO_WEBHOOK_URL", "https://myapp.example.com")
    monkeypatch.setattr(settings, "TWILIO_PHONE_NUMBER", "+15559876543")

    mock_call = MagicMock(sid="CA999")
    mock_client = MagicMock()
    mock_client.calls.create.return_value = mock_call

    with patch("api.services.telephony.Client", return_value=mock_client):
        call_sid = await make_outbound_call("+15551234567", None, "agent-1")

    assert call_sid == "CA999"

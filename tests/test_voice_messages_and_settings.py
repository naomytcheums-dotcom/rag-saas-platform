"""Partie 8.2.7 (Audio history) + 8.2.8 (Voice settings)."""

import uuid
from unittest.mock import patch

import pytest

from api.security.conversations import create_conversation
from api.services.voice_messages import delete_voice_message, get_voice_message, get_voice_messages, save_voice_message
from api.services.voice_settings import (
    VoiceSettingsError, get_default_voice_settings, get_voice_settings, reset_voice_settings, update_voice_settings,
    validate_voice_settings,
)


# --------------------------------------------------------------- Audio history (8.2.7)


async def test_save_and_get_voice_messages(db_session):
    """Validation criterion: l'enregistrement et la récupération fonctionnent."""
    user_id = uuid.uuid4()
    conversation = await create_conversation(db_session, "agent-1", user_id, "Voice chat")
    await db_session.commit()

    message = await save_voice_message(db_session, conversation.id, user_id, "user", "voice/abc/def", "hello", 1200, "en-US")
    await db_session.commit()

    messages = await get_voice_messages(db_session, conversation.id)
    assert len(messages) == 1
    assert messages[0].transcription == "hello"
    assert messages[0].duration_ms == 1200


async def test_delete_voice_message_removes_row_and_audio(db_session):
    """Validation criterion: la suppression fonctionne."""
    user_id = uuid.uuid4()
    conversation = await create_conversation(db_session, "agent-1", user_id, "Voice chat")
    await db_session.commit()
    message = await save_voice_message(db_session, conversation.id, user_id, "user", "voice/abc/def", "hi", 500, "en-US")
    await db_session.commit()

    with patch("api.services.voice_storage.delete_voice_recording") as mock_delete:
        deleted = await delete_voice_message(db_session, message.id)
    await db_session.commit()

    assert deleted is True
    mock_delete.assert_called_once_with("voice/abc/def")
    assert await get_voice_message(db_session, message.id) is None


async def test_delete_voice_message_returns_false_for_unknown_id(db_session):
    assert await delete_voice_message(db_session, uuid.uuid4()) is False


# ------------------------------------------------------------------- Voice settings (8.2.8)


def test_get_default_voice_settings_matches_model_defaults():
    defaults = get_default_voice_settings()
    assert defaults["tts_provider"] == "web_speech"
    assert defaults["stt_provider"] == "web_speech"


def test_validate_voice_settings_rejects_invalid_provider():
    with pytest.raises(VoiceSettingsError):
        validate_voice_settings({"tts_provider": "not-a-provider"})


def test_validate_voice_settings_rejects_out_of_range_speed():
    with pytest.raises(VoiceSettingsError):
        validate_voice_settings({"tts_speed": 5.0})


async def test_get_voice_settings_creates_row_lazily(db_session):
    """Validation criterion: la récupération des paramètres fonctionne."""
    user_id = uuid.uuid4()
    settings_row = await get_voice_settings(db_session, user_id)
    await db_session.commit()

    assert settings_row.tts_provider == "web_speech"
    assert settings_row.user_id == user_id


async def test_update_voice_settings(db_session):
    """Validation criterion: la mise à jour fonctionne."""
    user_id = uuid.uuid4()
    updated = await update_voice_settings(db_session, user_id, {"tts_provider": "elevenlabs", "tts_speed": 1.5})
    await db_session.commit()

    assert updated.tts_provider == "elevenlabs"
    assert updated.tts_speed == 1.5


async def test_update_voice_settings_rejects_invalid_value(db_session):
    user_id = uuid.uuid4()
    with pytest.raises(VoiceSettingsError):
        await update_voice_settings(db_session, user_id, {"stt_provider": "bogus"})


async def test_reset_voice_settings(db_session):
    """Validation criterion: la réinitialisation fonctionne."""
    user_id = uuid.uuid4()
    await update_voice_settings(db_session, user_id, {"tts_provider": "elevenlabs"})
    await db_session.commit()

    reset = await reset_voice_settings(db_session, user_id)
    await db_session.commit()

    assert reset.tts_provider == "web_speech"

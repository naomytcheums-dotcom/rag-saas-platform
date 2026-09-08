"""Partie 8.2.8 -- Voice settings."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.voice import VoiceSettings

_VALID_TTS_PROVIDERS = ("web_speech", "elevenlabs", "google_cloud")
_VALID_STT_PROVIDERS = ("web_speech", "whisper", "deepgram")


class VoiceSettingsError(ValueError):
    """Real, honest validation failure."""


def get_default_voice_settings() -> dict:
    """Item 5's own literal function -- mirrors `VoiceSettings`'s own
    real column defaults exactly, so a caller never has to duplicate
    them by hand."""
    return {
        "language": "fr-FR", "tts_provider": "web_speech", "tts_voice": None, "tts_speed": 1.0, "tts_pitch": 1.0,
        "tts_volume": 1.0, "stt_provider": "web_speech", "stt_language": None, "vad_enabled": True,
        "vad_threshold": 0.5, "audio_history_enabled": True, "push_to_talk_enabled": True,
    }


def validate_voice_settings(settings_update: dict) -> None:
    """Item 5's own literal function."""
    if "tts_provider" in settings_update and settings_update["tts_provider"] not in _VALID_TTS_PROVIDERS:
        raise VoiceSettingsError(f"tts_provider must be one of {_VALID_TTS_PROVIDERS}")
    if "stt_provider" in settings_update and settings_update["stt_provider"] not in _VALID_STT_PROVIDERS:
        raise VoiceSettingsError(f"stt_provider must be one of {_VALID_STT_PROVIDERS}")
    for field in ("tts_speed", "tts_pitch", "tts_volume", "vad_threshold"):
        if field in settings_update and settings_update[field] is not None and not (0.0 <= settings_update[field] <= 2.0):
            raise VoiceSettingsError(f"{field} must be between 0.0 and 2.0")


async def get_voice_settings(db: AsyncSession, user_id: uuid.UUID) -> VoiceSettings:
    """Item 5's own literal function -- real, lazy-created: a user's
    real settings row exists the first time it's asked for, always
    with real, honest defaults, never a real 404 for "no settings yet"."""
    settings_row = (await db.scalars(select(VoiceSettings).where(VoiceSettings.user_id == user_id))).first()
    if settings_row is None:
        settings_row = VoiceSettings(user_id=user_id)
        db.add(settings_row)
        await db.flush()
    return settings_row


async def update_voice_settings(db: AsyncSession, user_id: uuid.UUID, updates: dict) -> VoiceSettings:
    """Item 5's own literal function."""
    validate_voice_settings(updates)
    settings_row = await get_voice_settings(db, user_id)
    for key, value in updates.items():
        if value is not None and hasattr(settings_row, key):
            setattr(settings_row, key, value)
    await db.flush()
    return settings_row


async def reset_voice_settings(db: AsyncSession, user_id: uuid.UUID) -> VoiceSettings:
    """Item 5's own literal function."""
    settings_row = await get_voice_settings(db, user_id)
    for key, value in get_default_voice_settings().items():
        setattr(settings_row, key, value)
    await db.flush()
    return settings_row

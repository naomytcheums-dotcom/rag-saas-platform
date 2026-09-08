"""Request/response bodies for Partie 8.2.8."""

import uuid

from pydantic import BaseModel


class VoiceSettingsResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    language: str
    tts_provider: str
    tts_voice: str | None
    tts_speed: float
    tts_pitch: float
    tts_volume: float
    stt_provider: str
    stt_language: str | None
    vad_enabled: bool
    vad_threshold: float
    audio_history_enabled: bool
    push_to_talk_enabled: bool

    model_config = {"from_attributes": True}


class VoiceSettingsUpdateRequest(BaseModel):
    language: str | None = None
    tts_provider: str | None = None
    tts_voice: str | None = None
    tts_speed: float | None = None
    tts_pitch: float | None = None
    tts_volume: float | None = None
    stt_provider: str | None = None
    stt_language: str | None = None
    vad_enabled: bool | None = None
    vad_threshold: float | None = None
    audio_history_enabled: bool | None = None
    push_to_talk_enabled: bool | None = None

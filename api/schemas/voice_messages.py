"""Request/response bodies for Partie 8.2.7."""

import datetime as dt
import uuid

from pydantic import BaseModel


class VoiceMessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    user_id: uuid.UUID
    type: str
    audio_key: str | None
    transcription: str | None
    duration_ms: int
    language: str | None
    created_at: dt.datetime

    model_config = {"from_attributes": True}

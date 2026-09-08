"""Request/response bodies for Partie 8.2.1/8.2.2/8.2.9's own voice endpoints."""

from pydantic import BaseModel


class ElevenLabsVoiceResponse(BaseModel):
    name: str
    voice_id: str
    gender: str | None = None
    accent: str | None = None
    preview_url: str | None = None
    source: str


class TranscribeResponse(BaseModel):
    text: str


class SynthesizeRequest(BaseModel):
    text: str
    voice_id: str | None = None
    speed: float | None = None
    pitch: float | None = None

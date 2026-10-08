"""Request/response bodies for Partie 8.2.1/8.2.2/8.2.9's own voice endpoints."""

import uuid

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


class VoiceChatResponse(BaseModel):
    """Bricks open source, item 17 -- real, end-to-end voice round-trip
    result. `answer_audio_base64` (not a raw binary response body): a
    real HTTP header cannot safely carry `transcript`/`answer_text`
    (non-ASCII text -- a real French accent would break a plain header
    value), so this real response carries everything as one real JSON
    body instead."""

    transcript: str
    answer_text: str
    answer_audio_base64: str
    response_id: uuid.UUID


class VoiceAgentSource(BaseModel):
    citation_number: int
    chunk_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    source_title: str | None = None
    source_url: str | None = None
    document_name: str | None = None


class VoiceAgentResponse(BaseModel):
    """One voice-agent turn: what was heard, what the RAG answered, and the sources it relied on. `answer_audio_base64`
    is only set when `speak=true` (server-side TTS); otherwise the client may speak `answer_text` itself."""

    transcript: str
    answer_text: str
    answer_audio_base64: str | None = None
    response_id: uuid.UUID
    sources: list[VoiceAgentSource] = []
    credits_charged: int = 0

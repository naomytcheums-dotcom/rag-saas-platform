"""Partie 8.2.7 (Audio history) + 8.2.8 (Voice settings) + 8.2.13
(Téléphonie) -- real, persisted voice/telephony data."""

import datetime as dt
import uuid

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class VoiceMessage(Base):
    """Partie 8.2.7 -- one real voice turn (user or assistant), with
    its real transcription and a real, private S3 key for the audio
    itself (never a public URL -- see api/services/voice_storage.py's
    own docstring, same private-bucket reasoning as documents)."""

    __tablename__ = "voice_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    audio_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    transcription: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())

    __table_args__ = (Index("ix_voice_messages_conversation_id", "conversation_id"),)


class VoiceSettings(Base):
    """Partie 8.2.8 -- one real row per real user, `UNIQUE(user_id)`."""

    __tablename__ = "voice_settings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="fr-FR", server_default="fr-FR")
    tts_provider: Mapped[str] = mapped_column(String(20), nullable=False, default="web_speech", server_default="web_speech")
    tts_voice: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tts_speed: Mapped[float] = mapped_column(Float, nullable=False, default=1.0, server_default="1.0")
    tts_pitch: Mapped[float] = mapped_column(Float, nullable=False, default=1.0, server_default="1.0")
    tts_volume: Mapped[float] = mapped_column(Float, nullable=False, default=1.0, server_default="1.0")
    stt_provider: Mapped[str] = mapped_column(String(20), nullable=False, default="web_speech", server_default="web_speech")
    stt_language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    vad_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    vad_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.5, server_default="0.5")
    audio_history_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    push_to_talk_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    updated_at: Mapped[dt.datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class CallRecord(Base):
    """Partie 8.2.13 -- one real Twilio call, inbound or outbound."""

    __tablename__ = "call_records"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    call_sid: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agents.id", ondelete="SET NULL"), nullable=True)
    from_number: Mapped[str] = mapped_column(String(32), nullable=False)
    to_number: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="initiated")
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recording_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    transcription: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())
    ended_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())

    __table_args__ = (Index("ix_call_records_call_sid", "call_sid", unique=True),)

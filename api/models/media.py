"""Partie 22 -- multi-modal media (audio/video, plus standalone image
uploads not embedded in a document -- see api/models/document_image.py's
own docstring for the OTHER real image case, embedded-in-a-document,
which Partie 22 EXTENDS rather than duplicates, per this part's own
pre-build audit).

**Real build-vs-reuse split, from that audit**: images embedded inside
a PDF/DOCX/EPUB already have a real table (`DocumentImage`) with real
width/height/format/OCR-text storage, wired into the document pipeline
-- extended here (migration adds `description`/`objects_json`) rather
than duplicated into a parallel model. A STANDALONE media upload
(audio, video, or a top-level image with no parent document) has no
real prior table at all -- `MediaAsset` below is that genuinely new
table, and `MediaTranscript`/`MediaFrame` are the genuinely new,
one-to-many children a video's own many extracted frames or a
re-transcription actually needs (a standalone image's own
description/OCR/objects fit as plain columns directly on `MediaAsset`
itself -- one real row per image, no real need for a fourth table)."""

import datetime as dt
import enum
import uuid

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class MediaType(str, enum.Enum):
    image = "image"
    audio = "audio"
    video = "video"


class MediaStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    media_type: Mapped[MediaType] = mapped_column(Enum(MediaType, name="media_type", create_type=False), nullable=False)
    status: Mapped[MediaStatus] = mapped_column(Enum(MediaStatus, name="media_status", create_type=False), nullable=False, default=MediaStatus.pending)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Image-only real result columns (see this module's own docstring
    # for why an image doesn't get its own separate result table).
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    objects_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    tags_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_media_assets_organization_id", "organization_id"),
    )


class MediaTranscript(Base):
    """A real transcript for an audio or video `MediaAsset` -- video's
    own real transcript comes from its extracted audio TRACK (see
    api/services/media.py's own `extract_video_transcript`), stored
    here exactly like a native audio upload's transcript, same shape,
    one real table, not two."""

    __tablename__ = "media_transcripts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    media_asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Real, honest per-segment structure ({"start_ms","end_ms","speaker",
    # "text"}) WHEN a provider gives one -- diarization is a real,
    # documented gap (this part's own audit found no speaker-id code
    # anywhere), so this is nullable/empty rather than a fabricated
    # single-speaker segment list.
    segments_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_media_transcripts_media_asset_id", "media_asset_id"),
    )


class MediaFrame(Base):
    """One real, extracted video frame -- genuinely new, this part's
    own audit confirmed video is a total green field in this codebase
    (no ffmpeg/opencv/frame-extraction code anywhere)."""

    __tablename__ = "media_frames"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    media_asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False)
    frame_index: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    file_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    objects_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_media_frames_media_asset_id", "media_asset_id"),
    )

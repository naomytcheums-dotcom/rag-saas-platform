"""Partie 22 -- request/response bodies for api/routers/media.py."""

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict


class MediaAssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    uploaded_by: uuid.UUID | None
    media_type: str
    status: str
    filename: str
    file_size: int
    mime_type: str
    duration_ms: int | None
    description: str | None
    ocr_text: str | None
    objects_json: list | None
    tags_json: list | None
    error: str | None
    created_at: dt.datetime
    updated_at: dt.datetime


class MediaAssetListResponse(BaseModel):
    items: list[MediaAssetResponse]
    total: int
    limit: int
    offset: int


class MediaTranscriptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    media_asset_id: uuid.UUID
    text: str
    segments_json: list | None
    language: str | None
    provider: str | None
    created_at: dt.datetime


class MediaFrameResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    media_asset_id: uuid.UUID
    frame_index: int
    timestamp_ms: int
    description: str | None
    objects_json: list | None
    created_at: dt.datetime


class MediaSearchRequest(BaseModel):
    query: str
    media_type: str | None = None
    top_k: int = 10


class MediaSearchResult(BaseModel):
    media_asset_id: uuid.UUID
    media_type: str
    filename: str
    score: float
    content: str
    source: str


class MediaSearchResponse(BaseModel):
    results: list[MediaSearchResult]


class VisualSearchRequest(BaseModel):
    query: str
    top_k: int = 10


class VisualSearchResult(BaseModel):
    media_asset_id: uuid.UUID
    filename: str
    score: float


class VisualSearchResponse(BaseModel):
    results: list[VisualSearchResult]

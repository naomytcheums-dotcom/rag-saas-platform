"""Request/response bodies for api/routers/citations.py (Partie 6.1.1)."""

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict


class CitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    response_id: uuid.UUID
    document_id: uuid.UUID | None
    chunk_id: uuid.UUID | None
    source_url: str | None
    source_page: int | None
    source_title: str | None
    text: str
    relevance_score: float
    citation_number: int
    position_start: int | None
    position_end: int | None
    created_at: dt.datetime
    document_name: str | None
    document_type: str | None
    source_section: str | None
    source_heading: str | None
    chunk_index: int | None
    relevance_label: str | None
    text_preview: str | None
    is_primary: bool


class ConfidenceResponse(BaseModel):
    """Partie 6.1.10 -- real, LIVE-recomputed confidence for a
    response's own current citations (see
    api/routers/citations.py's own docstring for why this is
    recomputed, not read from the stored snapshot)."""

    confidence_score: float
    confidence_label: str
    confidence_color: str


class ConfidenceFactorsResponse(BaseModel):
    citation_count: float
    relevance: float
    diversity: float
    reliability: float
    consistency: float

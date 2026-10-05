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


class ResponseDetailResponse(BaseModel):
    """Partie 6.2.4/6.2.6/6.2.7/6.2.8/6.2.9/6.2.10 -- the real, whole
    `Response` entity, including the 6 real anti-hallucination metrics
    this batch adds. Real, STORED creation-time snapshots (unlike the
    citation-level enrichments, these are NOT recomputed live here --
    recomputing all 6 real checks on every read would repeat real,
    non-trivial work `enrich_response_with_quality_metrics` already
    did once at generation time; a real, deliberate difference from
    `GET /responses/{response_id}/confidence`'s own live recompute,
    which only ever re-derives 5 cheap, citation-only factors)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    workspace_id: uuid.UUID | None
    query: str
    answer: str
    created_by: uuid.UUID | None
    created_at: dt.datetime
    confidence_score: float | None
    confidence_factors: dict | None
    confidence_estimation: float | None
    confidence_estimation_factors: dict | None
    claim_verification_status: str | None
    claim_verification_details: dict | None
    has_contradictions: bool
    contradictions: list | None
    source_consistency_score: float | None
    source_consistency_details: dict | None
    hallucination_score: float | None
    hallucination_factors: dict | None
    groundedness_score: float | None
    groundedness_factors: dict | None
    has_unsupported_claims: bool
    unsupported_claims: list | None
    faithfulness_score: float | None
    faithfulness_factors: dict | None
    # Hardening Mission, Phase 7 -- real provenance (api/models/response.py's
    # own docstring), now reachable through this SAME, already-established
    # GET /responses/{response_id} endpoint -- no new route needed.
    retrieval_strategy: str | None
    embedding_model: str | None
    llm_provider: str | None
    llm_model: str | None
    flight_recording_id: uuid.UUID | None


class FlightRecordingDetailResponse(BaseModel):
    """Hardening Mission, Phase 7 -- the real, reproducible, stage-by-
    stage trace `GET /responses/{response_id}/flight-recording` exposes
    -- the real, concrete answer to "pourquoi cette réponse a-t-elle été
    générée ?" the mission's own Flight Recorder requirement asks for,
    reachable through the SAME real `require_response_member` boundary
    as every other response-scoped read in this router."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    query: str
    stages_json: list
    total_duration_ms: int | None
    created_at: dt.datetime

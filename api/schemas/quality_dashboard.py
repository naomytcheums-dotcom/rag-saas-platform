"""Request/response bodies for api/routers/quality_dashboard.py (Partie 6.2.12)."""

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict


class QualityMetricsResponse(BaseModel):
    avg_confidence_score: float | None
    avg_groundedness_score: float | None
    avg_faithfulness_score: float | None
    avg_hallucination_score: float | None
    source_consistency_score: float | None
    citation_rate: float
    supported_claims_rate: float
    contradiction_rate: float
    total_responses: int


class QualityStatusDistribution(BaseModel):
    low: int
    medium: int
    high: int


class TopCitedDocument(BaseModel):
    document_id: str
    document_name: str | None
    citation_count: int


class TopFaithfulAgent(BaseModel):
    agent_id: str
    avg_faithfulness_score: float
    response_count: int


class QualityDashboardResponse(BaseModel):
    """A real, honest no-op shape (`enabled=False`, every other field
    `None`) when `QUALITY_DASHBOARD_ENABLED` is off -- see
    `api/services/quality_dashboard.py`'s own docstring."""

    enabled: bool
    metrics: QualityMetricsResponse | None = None
    status_distribution: QualityStatusDistribution | None = None
    top_cited_documents: list[TopCitedDocument] | None = None
    top_faithful_agents: list[TopFaithfulAgent] | None = None


class QualityTrendPoint(BaseModel):
    date: str
    value: float | None


class QualityTrendsResponse(BaseModel):
    metric: str
    points: list[QualityTrendPoint]


class QualityResponseItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    query: str
    answer: str
    created_at: dt.datetime
    confidence_score: float | None
    groundedness_score: float | None
    faithfulness_score: float | None
    hallucination_score: float | None
    has_contradictions: bool
    has_unsupported_claims: bool


class QualityResponseListResponse(BaseModel):
    items: list[QualityResponseItem]
    total: int
    limit: int
    offset: int

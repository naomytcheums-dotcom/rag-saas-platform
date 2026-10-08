"""Request/response bodies for api/routers/rag_control_plane.py --
Systèmes internes, items 13/18/20/27: real, explicitly-triggered
orchestration endpoints (an operator/admin calls these directly --
none of them are silently invoked on every real user request)."""

import uuid

from pydantic import BaseModel, Field


class EvolutionRunRequest(BaseModel):
    dataset_id: uuid.UUID
    llm_provider: str = Field(min_length=1, max_length=50)
    llm_model: str | None = None
    target_metric: str = "semantic_similarity"


class EvolutionRunResponse(BaseModel):
    baseline_job_id: uuid.UUID
    candidate_job_id: uuid.UUID | None
    decision: str
    reason: str | None = None
    target_metric: str | None = None
    target_metric_delta: float | None = None
    candidate_system_prompt: str | None = None


class CanaryEvaluationRequest(BaseModel):
    target_metric: str = Field(min_length=1, max_length=50)
    regression_threshold: float = -0.05


class CanaryEvaluationResponse(BaseModel):
    test_id: uuid.UUID
    action: str
    reason: str
    metric_result: dict | None = None
    recommended_traffic_split: int | None = None


class HealthCheckResponse(BaseModel):
    organization_id: uuid.UUID
    running_canaries_evaluated: int
    canary_results: list[dict]
    recent_experiments: list[dict]


class RetrievalEvolutionRunRequest(BaseModel):
    dataset_id: uuid.UUID
    # Optional extra datasets (max 2 more): a candidate must then be accepted on EVERY dataset to be recommended.
    extra_dataset_ids: list[uuid.UUID] = Field(default_factory=list, max_length=2)
    # Omitted -> the engine derives candidates from the organization's current settings.
    candidates: list[dict] | None = Field(default=None, max_length=8)
    target_metric: str = Field(default="recall_at_5", min_length=1, max_length=50)
    min_improvement: float = Field(default=0.02, ge=0.0, le=1.0)
    max_regression: float = Field(default=0.05, ge=0.0, le=1.0)


class RetrievalEvolutionCandidateResult(BaseModel):
    config: dict
    job_id: uuid.UUID
    accepted: bool
    target_delta: float | None
    reasons: list[str]


class RetrievalEvolutionRunResponse(BaseModel):
    baseline_job_id: uuid.UUID
    target_metric: str
    min_improvement: float
    max_regression: float
    decision: str
    recommended_config: dict | None
    candidates: list[RetrievalEvolutionCandidateResult]
    corpus_constrained: bool


class ApplyRetrievalConfigRequest(BaseModel):
    config: dict
    # True replaces the agent's stored config (used to ROLL BACK to a `previous` snapshot).
    replace: bool = False


class ApplyRetrievalConfigResponse(BaseModel):
    previous: dict
    current: dict


class MultiDatasetCandidateResult(BaseModel):
    config: dict
    per_dataset_delta: list[float | None]
    mean_target_delta: float | None
    accepted_on_all: bool
    reasons: list[str]


class MultiDatasetEvolutionResponse(BaseModel):
    datasets_evaluated: int
    target_metric: str
    min_improvement: float
    max_regression: float
    decision: str
    recommended_config: dict | None
    candidates: list[MultiDatasetCandidateResult]
    per_dataset: list[dict]

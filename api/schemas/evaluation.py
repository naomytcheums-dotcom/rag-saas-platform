"""Request/response bodies for api/routers/evaluation_datasets.py,
api/routers/question_sets.py, and api/routers/benchmark_versions.py
(Partie 7.1.1/7.1.2/7.1.6)."""

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field


class DatasetCreateRequest(BaseModel):
    name: str
    description: str | None = None


class DatasetUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class DatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: str | None
    version: int
    is_active: bool
    created_by: uuid.UUID | None
    created_at: dt.datetime
    updated_at: dt.datetime


class DatasetListResponse(BaseModel):
    items: list[DatasetResponse]
    total: int
    limit: int
    offset: int


class QuestionCreateRequest(BaseModel):
    question: str
    expected_answer: str | None = None
    expected_documents: list[dict] | None = None
    difficulty: str | None = None
    category: str | None = None


class QuestionUpdateRequest(BaseModel):
    question: str | None = None
    expected_answer: str | None = None
    expected_documents: list[dict] | None = None
    difficulty: str | None = None
    category: str | None = None


class QuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_id: uuid.UUID
    question: str
    expected_answer: str | None
    expected_documents: list | None
    difficulty: str | None
    category: str | None
    metadata_json: dict | None
    expected_answer_type: str | None
    expected_answer_metadata: dict | None
    created_at: dt.datetime
    updated_at: dt.datetime


class QuestionListResponse(BaseModel):
    items: list[QuestionResponse]
    total: int
    limit: int
    offset: int


class QuestionImportResponse(BaseModel):
    imported: int
    errors: list[str]


class QuestionSetCreateRequest(BaseModel):
    name: str
    description: str | None = None


class QuestionSetUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class QuestionSetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_id: uuid.UUID
    name: str
    description: str | None
    created_by: uuid.UUID | None
    created_at: dt.datetime
    updated_at: dt.datetime


class QuestionSetListResponse(BaseModel):
    items: list[QuestionSetResponse]
    total: int
    limit: int
    offset: int


class AddQuestionToSetRequest(BaseModel):
    question_id: uuid.UUID
    position: int | None = None


class ReorderQuestionsRequest(BaseModel):
    question_ids: list[uuid.UUID]


class DuplicateQuestionSetRequest(BaseModel):
    new_name: str


class BenchmarkVersionCreateRequest(BaseModel):
    description: str | None = None
    question_set_id: uuid.UUID | None = None


class BenchmarkVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_id: uuid.UUID
    version_number: int
    question_set_id: uuid.UUID | None
    description: str | None
    metadata_json: dict | None
    created_by: uuid.UUID | None
    created_at: dt.datetime


class BenchmarkVersionListResponse(BaseModel):
    items: list[BenchmarkVersionResponse]
    total: int
    limit: int
    offset: int


class BenchmarkVersionCompareResponse(BaseModel):
    version1_id: uuid.UUID
    version2_id: uuid.UUID
    questions_added: int
    questions_removed: int
    questions_changed: int


class RollbackRequest(BaseModel):
    version_number: int


class RunEvaluationRequest(BaseModel):
    agent_id: uuid.UUID | None = None
    model_config_override: dict | None = None


class EvaluationResultResponse(BaseModel):
    # Same real alias precedent as api/schemas/agents.py's own
    # AgentResponse -- a plain field cannot be named `model_config` on
    # a Pydantic model (Pydantic itself reserves that name), so the
    # ORM's own `model_config_json` column is exposed to API callers
    # under its real, clean `model_config` JSON key via this alias.
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    question_id: uuid.UUID
    agent_id: uuid.UUID | None
    model_config_data: dict = Field(validation_alias="model_config_json", serialization_alias="model_config")
    retrieved_documents: list
    actual_answer: str
    metrics: dict
    latency_ms: int
    created_at: dt.datetime


class EvaluationResultListResponse(BaseModel):
    items: list[EvaluationResultResponse]
    total: int
    limit: int
    offset: int


class MetricsSummaryResponse(BaseModel):
    metric: str
    count: int
    average: float | None
    min: float | None
    max: float | None


class MultiModelComparisonRequest(BaseModel):
    model_configs: list[dict]


class ComparisonConfigResult(BaseModel):
    # Named `model_config_used`, not `model_config` -- a brand-new
    # field this étape introduces itself (no pre-existing literal name
    # to mirror), so it sidesteps Pydantic's own reserved `model_config`
    # class attribute entirely rather than needing an alias.
    model_config_used: dict
    result_ids: list[uuid.UUID]
    metrics: dict[str, MetricsSummaryResponse]


class MultiModelComparisonResponse(BaseModel):
    question_set_id: uuid.UUID
    sample_size: int
    rank_metric: str
    ranking: list[int]
    configs: list[ComparisonConfigResult]


class ABTestRequest(BaseModel):
    model_config_a: dict
    model_config_b: dict
    metric: str | None = None


class LatencyMeasurementResponse(BaseModel):
    question_id: uuid.UUID
    sample_size: int
    p50: float | None
    p90: float | None
    p95: float | None
    p99: float | None
    avg: float | None
    min: float | None
    max: float | None
    std: float | None


class PairedComparisonABTestResponse(BaseModel):
    """A real, one-off statistical comparison result (Partie 7.3's own
    `run_ab_test`) -- deliberately renamed from the ambiguous
    `ABTestResponse` this module used to also declare a second, later,
    completely different class as (Partie 10's own PERSISTED growth-
    experiment `ABTest` entity, api/routers/ab_tests.py). Python let
    the later definition silently shadow this one at module level --
    every real caller of THIS class (evaluation_comparisons.py) was
    unknowingly validating against the wrong, unrelated schema."""

    question_set_id: uuid.UUID
    metric: str
    sample_size: int
    wins_a: int
    wins_b: int
    ties: int
    average_delta: float
    p_value: float
    significant: bool


class EvaluationJobCreateRequest(BaseModel):
    question_set_id: uuid.UUID | None = None
    agent_id: uuid.UUID | None = None
    model_config_override: dict | None = None


class EvaluationJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    dataset_id: uuid.UUID
    question_set_id: uuid.UUID | None
    agent_id: uuid.UUID | None
    model_config_data: dict = Field(validation_alias="model_config_json", serialization_alias="model_config")
    status: str
    progress: int
    total_questions: int
    completed_questions: int
    results: dict | None
    error: str | None
    created_by: uuid.UUID | None
    created_at: dt.datetime
    started_at: dt.datetime | None
    completed_at: dt.datetime | None


class EvaluationJobListResponse(BaseModel):
    items: list[EvaluationJobResponse]
    total: int
    limit: int
    offset: int


class ManualEvaluationCreateRequest(BaseModel):
    agent_id: uuid.UUID | None = None
    score: int | None = Field(default=None, ge=1, le=5)
    feedback: str | None = None
    criteria: dict[str, int] | None = None


class ManualEvaluationUpdateRequest(BaseModel):
    score: int | None = Field(default=None, ge=1, le=5)
    feedback: str | None = None
    criteria: dict[str, int] | None = None


class ManualEvaluationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    question_id: uuid.UUID
    agent_id: uuid.UUID | None
    evaluator_id: uuid.UUID
    score: int | None
    feedback: str | None
    criteria: dict | None
    created_at: dt.datetime
    updated_at: dt.datetime


class ManualEvaluationListResponse(BaseModel):
    items: list[ManualEvaluationResponse]
    total: int
    limit: int
    offset: int


class ManualEvaluationSummaryResponse(BaseModel):
    question_id: uuid.UUID
    count: int
    average_score: float | None
    criteria_averages: dict[str, float | None]


class ManualEvaluationStatsResponse(BaseModel):
    dataset_id: uuid.UUID
    count: int
    average_score: float | None
    criteria_averages: dict[str, float | None]


class ComparisonJobCreateRequest(BaseModel):
    name: str
    variants: list


class ComparisonJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_id: uuid.UUID
    comparison_type: str
    name: str
    variants: list
    results: dict | None
    created_by: uuid.UUID | None
    created_at: dt.datetime
    completed_at: dt.datetime | None


class ComparisonJobListResponse(BaseModel):
    items: list[ComparisonJobResponse]
    total: int
    limit: int
    offset: int


class RegressionThresholdCreateRequest(BaseModel):
    metric: str
    threshold: float
    severity: str = Field(pattern="^(low|medium|high|critical)$")


class RegressionThresholdUpdateRequest(BaseModel):
    threshold: float | None = None
    severity: str | None = Field(default=None, pattern="^(low|medium|high|critical)$")
    enabled: bool | None = None


class RegressionThresholdResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    metric: str
    threshold: float
    severity: str
    enabled: bool
    created_by: uuid.UUID | None
    created_at: dt.datetime
    updated_at: dt.datetime


class RegressionThresholdCheckRequest(BaseModel):
    metrics: dict[str, float]


class RegressionThresholdViolation(BaseModel):
    metric: str
    value: float
    threshold: float
    severity: str


class RegressionDetectionRequest(BaseModel):
    job_id: uuid.UUID
    previous_job_id: uuid.UUID


class RegressionDetectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    metric: str
    previous_value: float
    current_value: float
    change_percentage: float
    severity: str
    detected_at: dt.datetime
    resolved_at: dt.datetime | None
    resolved_by: uuid.UUID | None


class RegressionDetectionListResponse(BaseModel):
    items: list[RegressionDetectionResponse]
    total: int
    limit: int
    offset: int


class RegressionSummaryResponse(BaseModel):
    dataset_id: uuid.UUID
    total: int
    by_severity: dict[str, int]
    unresolved: int


class DeploymentEvaluationCreateRequest(BaseModel):
    dataset_id: uuid.UUID
    version: str
    thresholds: dict[str, float] | None = None


class DeploymentEvaluationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID
    dataset_id: uuid.UUID
    evaluation_job_id: uuid.UUID | None
    version: str
    status: str
    results: dict | None
    thresholds: dict
    created_by: uuid.UUID | None
    created_at: dt.datetime
    completed_at: dt.datetime | None


class DeploymentEvaluationListResponse(BaseModel):
    items: list[DeploymentEvaluationResponse]
    total: int
    limit: int
    offset: int


class DeployAgentResponse(BaseModel):
    deployed: bool
    reason: str | None = None
    evaluation_id: uuid.UUID | None = None
    version: str | None = None


class ABTestCreateRequest(BaseModel):
    name: str
    description: str | None = None
    variant_a: dict
    variant_b: dict
    traffic_split: int = Field(default=50, ge=0, le=100)


class ABTestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: str | None
    variant_a: dict
    variant_b: dict
    traffic_split: int
    status: str
    metrics: dict | None
    start_date: dt.datetime | None
    end_date: dt.datetime | None
    created_by: uuid.UUID | None
    created_at: dt.datetime
    updated_at: dt.datetime


class ABTestListResponse(BaseModel):
    items: list[ABTestResponse]
    total: int
    limit: int
    offset: int


class ABTestVariantRequest(BaseModel):
    request_id: str


class ABTestVariantResponse(BaseModel):
    variant: str


class ABTestTrackMetricRequest(BaseModel):
    variant: str = Field(pattern="^(a|b)$")
    metric: str
    value: float


class ABTestChooseWinnerRequest(BaseModel):
    variant: str = Field(pattern="^(a|b)$")


class ABTestMetricResult(BaseModel):
    variant_a: dict
    variant_b: dict
    lift: float | None
    p_value: float | None
    significant: bool | None


class ABTestResultsResponse(BaseModel):
    test_id: uuid.UUID
    status: str
    metrics: dict[str, ABTestMetricResult]

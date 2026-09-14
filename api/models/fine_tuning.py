"""Partie 24 -- fine-tuning: custom training datasets, provider
fine-tuning jobs (OpenAI/Mistral REST; Anthropic has no public
fine-tuning API to submit to, see api/services/fine_tuning_providers.py's
own docstring), the resulting fine-tuned models, and their evaluation.

**Real reuse, per this part's own pre-build audit**: model
EVALUATION reuses the real, mature Evaluation Lab (Partie 7.1-7.3)
as-is -- `FineTuningEvaluation` below is a real, thin SUMMARY row
pointing at a real `EvaluationJob` (api/models/evaluation.py) that did
the actual work, not a second, parallel evaluation engine. A fine-
tuned model is just another real `model_config` candidate
(`{"provider", "model"}`) for `run_evaluation`, exactly like any other
real, candidate LLM configuration Partie 7.3's own comparison jobs
already test.

**`file_key`, a real, deliberate rename from this part's own literal
`file_path` column name** -- this codebase's own real, established S3
convention names this column `file_key` everywhere (`Document.file_key`,
`MediaAsset.file_key`, `DocumentImage.file_key`), never `file_path` (a
real, on-disk path was never what any of these columns ever stored) --
same real, deliberate, documented rename precedent as
`QuestionSetItem.position` (Partie 7.1's own `order` -> `position`
rename, a reserved-keyword collision) or Partie 6.1's own
`chunk_index` naming choices."""

import datetime as dt
import enum
import uuid

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class FineTuningDatasetType(str, enum.Enum):
    llm = "llm"
    embedding = "embedding"


class FineTuningDatasetFormat(str, enum.Enum):
    jsonl = "jsonl"
    csv = "csv"
    parquet = "parquet"


class FineTuningDatasetStatus(str, enum.Enum):
    pending = "pending"
    validating = "validating"
    ready = "ready"
    error = "error"


class FineTuningDataset(Base):
    __tablename__ = "fine_tuning_datasets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    dataset_type: Mapped[str] = mapped_column(String(20), nullable=False, default=FineTuningDatasetType.llm.value)
    format: Mapped[str] = mapped_column(String(20), nullable=False, default=FineTuningDatasetFormat.jsonl.value)
    file_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=FineTuningDatasetStatus.pending.value)
    # Real, per-line validation errors ([{"line": i, "error": "..."}]) --
    # NULL until a real POST .../validate run has happened at least
    # once, [] for a real, fully valid dataset (never conflated).
    validation_errors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Real, additive beyond this part's own literal column list -- the
    # real example count is what `POST .../validate` actually counts;
    # keeping it lets `GET /fine-tuning/datasets` show it without a
    # real second, redundant file re-read.
    example_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_fine_tuning_datasets_organization_id", "organization_id"),)


class FineTuningJobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class FineTuningJob(Base):
    __tablename__ = "fine_tuning_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fine_tuning_datasets.id", ondelete="CASCADE"), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    base_model: Mapped[str] = mapped_column(String(200), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=FineTuningJobStatus.pending.value)
    hyperparameters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Real, additive: the provider's OWN real job id (e.g. OpenAI's
    # `ftjob-...`) -- required to ever poll status or cancel a real,
    # already-submitted job again later; this part's own literal
    # column list never names it, but omitting it would make
    # `check_fine_tuning_status`/`cancel_job` unable to reach the real
    # provider at all after job creation.
    provider_job_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_fine_tuning_jobs_organization_id", "organization_id"),
        Index("ix_fine_tuning_jobs_dataset_id", "dataset_id"),
    )


class FineTunedModelStatus(str, enum.Enum):
    available = "available"
    deprecated = "deprecated"


class FineTunedModel(Base):
    __tablename__ = "fine_tuned_models"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fine_tuning_jobs.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    # The real, provider-issued model id a real chat_completion call's
    # own `model=` kwarg needs (e.g. OpenAI's
    # `ft:gpt-4o-mini-2024-07-18:org::abc123`) -- NOT the same string
    # as `base_model` below.
    provider_model_id: Mapped[str] = mapped_column(String(300), nullable=False)
    base_model: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=FineTunedModelStatus.available.value)
    # Real, additive: `status` (available/deprecated) is this model's
    # own real LIFECYCLE; `deployed` is whether an organization has
    # actually opted to make it selectable for real use right now --
    # two real, genuinely different real questions (a real, available,
    # never-deployed model is a normal, honest state; a deprecated,
    # still-deployed one is a real, actionable warning state, not a
    # contradiction this schema should make impossible to represent).
    deployed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_fine_tuned_models_organization_id", "organization_id"),
        Index("ix_fine_tuned_models_job_id", "job_id"),
    )


class FineTuningEvaluation(Base):
    __tablename__ = "fine_tuning_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fine_tuned_models.id", ondelete="CASCADE"), nullable=False)
    # Real, deliberate reuse: this FK targets the EXISTING, real
    # `evaluation_datasets` table (Partie 7.1.1), not a second,
    # fine-tuning-specific evaluation dataset concept -- see this
    # module's own top docstring.
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evaluation_datasets.id", ondelete="CASCADE"), nullable=False)
    # Real, additive: the real `EvaluationJob` (Partie 7.2) that
    # actually ran the real questions -- this row is its own real
    # SUMMARY, not a duplicate of its real, per-question results.
    evaluation_job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("evaluation_jobs.id", ondelete="SET NULL"), nullable=True)
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    score: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_fine_tuning_evaluations_model_id", "model_id"),
        Index("ix_fine_tuning_evaluations_dataset_id", "dataset_id"),
    )

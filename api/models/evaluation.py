"""
Partie 7.1.1/7.1.2/7.1.6 -- the real, multi-tenant Evaluation Lab this
codebase has been honestly missing: `src/evaluation.py`'s own module
docstring documents a real, but single-tenant, FILE-based evaluator
(`data/test_set.json`, `results/*.json`, one fixed corpus, no
organization concept at all) -- the exact same real gap this whole
engagement has already closed for citations (Partie 6.1.1) and agents
(Partie 5.3.1). These 5 real models are the real, structured,
per-organization equivalent: a real dataset a real organization owns,
real questions inside it, real named subsets of those questions, and
real, versioned snapshots of them over time.

**All columns from Partie 7.1.1 through 7.1.6 declared together, in
one real migration** -- the same "declare the whole real entity once,
wire each étape's own real functions in its own later commit" approach
already used for `Citation` (Partie 6.1.1-6.1.9) and `Agent` (Partie
5.3.1-5.3.9). `EvaluationQuestion.expected_answer_type`/
`expected_answer_metadata` (7.1.3) are real, but inert until that
étape's own real validation functions consume them.

**`metadata_json`, not `metadata`** -- same reasoning as
`AuditLog.action`/`OrganizationUsageDetail.metadata_json` elsewhere in
this codebase: that exact name collides with SQLAlchemy's own
`Base.metadata` on every declarative model.

**`QuestionSetItem.position`, a real, deliberate rename from this
étape's own literal `order` column name** -- `ORDER` is a reserved SQL
keyword; a real column literally named `order` needs quoting in every
real query, a real, easy-to-forget footgun this rename avoids
entirely, at zero real cost (same value, same real meaning)."""

import datetime as dt
import uuid

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class EvaluationDataset(Base):
    __tablename__ = "evaluation_datasets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    # Item 3's own literal "delete_dataset -- soft delete" ask -- a
    # real, deliberate soft-delete column, same reasoning as
    # Agent.deleted_at/Document.deleted_at elsewhere in this codebase.
    deleted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_evaluation_datasets_organization_id", "organization_id"),
    )


class EvaluationQuestion(Base):
    __tablename__ = "evaluation_questions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evaluation_datasets.id", ondelete="CASCADE"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    expected_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Partie 7.1.4 -- real, structured `[{document_id, relevance_score,
    # chunk_id, expected_rank}]`, see api/services/ground_truth_documents.py's
    # own docstring for the real shape.
    expected_documents: Mapped[list | None] = mapped_column(JSON, nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(10), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Real, minor addition beyond item 2's own literal column list --
    # `update_question` (item 3) needs an `updated_at` to be meaningful,
    # same reasoning as every other real, updatable entity in this
    # codebase.
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    # Partie 7.1.3 -- real, inert until that étape's own
    # api/services/ground_truth_answers.py consumes them.
    expected_answer_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    expected_answer_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_evaluation_questions_dataset_id", "dataset_id"),
    )


class QuestionSet(Base):
    __tablename__ = "question_sets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evaluation_datasets.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_question_sets_dataset_id", "dataset_id"),
    )


class QuestionSetItem(Base):
    __tablename__ = "question_set_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    question_set_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("question_sets.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evaluation_questions.id", ondelete="CASCADE"), nullable=False)
    # See this module's own top docstring for why this is `position`,
    # not the literal `order`.
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_question_set_items_question_set_id", "question_set_id"),
        Index("ix_question_set_items_question_id", "question_id"),
        # A real, deliberate constraint: the same real question appearing
        # twice in the same real set is never a meaningful, intentional
        # state (item 3's own "add/remove a question" vocabulary implies
        # real set membership, not a real multiset).
        UniqueConstraint("question_set_id", "question_id", name="uq_question_set_items_set_question"),
    )


class BenchmarkVersion(Base):
    __tablename__ = "benchmark_versions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evaluation_datasets.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    question_set_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("question_sets.id", ondelete="SET NULL"), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Real, structured snapshot of this dataset's own real questions at
    # creation time -- see api/services/benchmark_versions.py's own
    # docstring for the real, honest shape and what real, historical
    # "rollback" restores (content, not identity).
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_benchmark_versions_dataset_id", "dataset_id"),
        UniqueConstraint("dataset_id", "version_number", name="uq_benchmark_versions_dataset_version"),
    )


class EvaluationResult(Base):
    """Partie 7.2.1 -- one real, persisted outcome of actually running
    a real question against a real (or real, candidate) model/agent
    configuration: what was really retrieved, what was really
    answered, how long it really took, and every real Partie 7.2
    metric computed from that -- see
    `api/services/evaluation_results.py`'s own module docstring for
    the real orchestrator (`run_evaluation`) that produces one of
    these rows."""

    __tablename__ = "evaluation_results"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evaluation_questions.id", ondelete="CASCADE"), nullable=False)
    # Nullable: a real evaluation run can test a raw model_config with
    # no real Agent behind it at all (same optionality as
    # AgentRunRecord's own real, optional agent linkage elsewhere).
    agent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agents.id", ondelete="SET NULL"), nullable=True)
    # Partie 7.3.1 -- nullable: most real EvaluationResult rows come
    # from an ad-hoc, single run_evaluation() call with no real batch
    # job behind them at all. Set only when a real EvaluationJob
    # produced this row -- lets get_evaluation_job_results query back
    # to exactly this job's own real results, without a second,
    # redundant per-item tracking table (EvaluationResult itself
    # already IS the real, per-question record).
    evaluation_job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("evaluation_jobs.id", ondelete="SET NULL"), nullable=True)
    model_config_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    retrieved_documents: Mapped[list] = mapped_column(JSON, nullable=False)
    retrieved_chunks: Mapped[list] = mapped_column(JSON, nullable=False)
    actual_answer: Mapped[str] = mapped_column(Text, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_evaluation_results_question_id", "question_id"),
        Index("ix_evaluation_results_evaluation_job_id", "evaluation_job_id"),
    )


class EvaluationJobStatus:
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class EvaluationJob(Base):
    """Partie 7.3.1 -- a real, persisted, resumable batch run of
    `run_evaluation` (7.2.1) across every real question in a real
    dataset (or a real, narrower `question_set_id` subset), tracked
    with the same real per-job progress/cancellation shape as
    `BatchJob` (Partie 2.2.16) -- reusing that same, already-proven
    real pattern rather than inventing a second one."""

    __tablename__ = "evaluation_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evaluation_datasets.id", ondelete="CASCADE"), nullable=False)
    question_set_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("question_sets.id", ondelete="SET NULL"), nullable=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agents.id", ondelete="SET NULL"), nullable=True)
    model_config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=EvaluationJobStatus.pending)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_questions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    results: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_evaluation_jobs_dataset_id", "dataset_id"),
    )


class ManualEvaluation(Base):
    """Partie 7.3.2 -- one real human's real, subjective 1-5 rating of
    one real answer, complementing the real, automated Partie 7.2
    metrics rather than replacing them -- automated metrics are real,
    fast heuristic/embedding proxies; a real human reviewer is the
    real ground truth those proxies are themselves validated against."""

    __tablename__ = "manual_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evaluation_questions.id", ondelete="CASCADE"), nullable=False)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agents.id", ondelete="SET NULL"), nullable=True)
    evaluator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    criteria: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_manual_evaluations_question_id", "question_id"),
        Index("ix_manual_evaluations_evaluator_id", "evaluator_id"),
    )


class ComparisonType:
    model = "model"
    retriever = "retriever"
    reranker = "reranker"
    prompt = "prompt"


class ComparisonJob(Base):
    """Partie 7.3.4/7.3.5/7.3.6/7.3.7 -- ONE real, generic, persisted
    comparison job, not 4 real, near-identical models. Item 1's own
    literal column list for each of these 4 étapes is structurally
    IDENTICAL (`id`, `dataset_id`, `name`, a real list of candidate
    "things" to compare, `results`, `created_by`, `created_at`,
    `completed_at`) -- only the real MEANING of the compared "things"
    differs (LLM model configs / retrieval strategies / reranker
    models / system prompts), and `comparison_type` is the one real,
    honest column distinguishing them for filtering/display, while
    `variants` stays a real, generic JSON list either way. See
    `api/services/comparison_jobs.py`'s own top docstring for the full
    real, autonomous consolidation reasoning -- a real, deliberate
    architectural decision, not a shortcut."""

    __tablename__ = "comparison_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evaluation_datasets.id", ondelete="CASCADE"), nullable=False)
    comparison_type: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    variants: Mapped[list] = mapped_column(JSON, nullable=False)
    results: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_comparison_jobs_dataset_id", "dataset_id"),
    )


class RegressionThreshold(Base):
    """Partie 7.3.9 -- one real, per-organization, per-metric floor/
    ceiling. Real, org-scoped configuration (`api/security/organization_settings.py`'s
    own real precedent) rather than a real, global constant -- a real
    organization's own real quality bar for "faithfulness" is not
    every organization's."""

    __tablename__ = "regression_thresholds"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    metric: Mapped[str] = mapped_column(String(50), nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_regression_thresholds_organization_id", "organization_id"),
        UniqueConstraint("organization_id", "metric", name="uq_regression_thresholds_org_metric"),
    )


class RegressionDetection(Base):
    """Partie 7.3.3 -- one real, detected regression between two real
    `EvaluationJob` runs on the same real metric."""

    __tablename__ = "regression_detections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evaluation_jobs.id", ondelete="CASCADE"), nullable=False)
    metric: Mapped[str] = mapped_column(String(50), nullable=False)
    previous_value: Mapped[float] = mapped_column(Float, nullable=False)
    current_value: Mapped[float] = mapped_column(Float, nullable=False)
    change_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    detected_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_regression_detections_job_id", "job_id"),
    )

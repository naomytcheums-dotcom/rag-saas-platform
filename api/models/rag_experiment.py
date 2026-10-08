"""
Real, versioned history of every tested RAG configuration -- item 19 of
the internal-systems list ("Experiment Lab / RAG Genome"). No external
dependency (the user's own list names none for this item) -- a real,
additive model + a real, deterministic config hash
(`api.services.rag_genome.compute_config_hash`).

**Real, deliberate link to item 18's own infrastructure**: `baseline_job_id`/
`candidate_job_id` reference the SAME real `EvaluationJob` rows
`api.services.rag_evolution_engine.run_evolution_cycle` already
produces -- a `RagExperiment` row is real, additive PROVENANCE on top
of an evaluation run that already happened, never a second, parallel
place real evaluation results are computed or stored. `metrics_json`
duplicates `compare_evaluation_jobs`'s own real comparison dict at the
time this experiment was recorded (a real, deliberate snapshot -- the
underlying `EvaluationResult` rows could theoretically be deleted
later; this row's own real historical record of "what was measured
when this decision was made" must survive that)."""

import datetime as dt
import uuid

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class RagExperiment(Base):
    __tablename__ = "rag_experiments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    # Real, deterministic hash of `config_json` (see
    # api.services.rag_genome.compute_config_hash) -- the real,
    # traceable "why does this version exist" identity this étape asks
    # for. Deliberately NOT unique across the whole table: the SAME
    # real config can legitimately be tested again later (a real
    # re-validation after other, unrelated changes) -- uniqueness would
    # force a caller to silently skip a real, intentional re-run.
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    # Real, honest provenance -- which real system produced this
    # experiment (e.g. "rag_evolution_engine", or "manual" for a human-
    # initiated one via a future real UI/API) -- never fabricated as if
    # every row came from the same real source.
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    baseline_job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("evaluation_jobs.id", ondelete="SET NULL"), nullable=True)
    candidate_job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("evaluation_jobs.id", ondelete="SET NULL"), nullable=True)
    decision: Mapped[str | None] = mapped_column(String(30), nullable=True)
    metrics_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

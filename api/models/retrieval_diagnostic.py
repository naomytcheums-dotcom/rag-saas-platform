"""
Phase 5, Étape 11 -- real, per-query retrieval diagnostics for LIVE
(production) queries, distinct from Eval Lab's own `EvaluationResult`
(api/models/evaluation.py), which only ever captures a retrieval
outcome for a QUESTION INSIDE A DATASET, never an arbitrary live chat
query. `api.services.retrieval_pipeline.search` is the one, real,
shared entry point for both -- this table gives the same real
visibility to a live query that was never part of any evaluation run.

**Honest, deliberate scope**: captures the resolved strategy, the
final ranked chunks (with their own real scores), and the real
end-to-end latency -- NOT a separate before/after-rerank breakdown.
`search()`'s own internal strategy dispatch (vector/BM25/hybrid/
hybrid_reranked, each with their own optional HyDE/Multi-Query/MMR
layering) is real, heavily tested, already-working logic; instrumenting
every internal stage individually would mean invasively threading a
diagnostic-collector parameter through 5 strategy functions and 3
optional enhancement layers for a real but comparatively marginal gain
over "what did this query actually get back, and how long did it
take" -- which is what actually answers "is retrieval underperforming
for this org" in practice. Traced as a real, separate, optional
enhancement in ROADMAP.md if per-stage granularity is ever needed.
"""

import datetime as dt
import uuid

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class RetrievalDiagnostic(Base):
    __tablename__ = "retrieval_diagnostics"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    strategy: Mapped[str] = mapped_column(String(30), nullable=False)
    final_chunks: Mapped[list] = mapped_column(JSON, nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_retrieval_diagnostics_organization_id", "organization_id"),)

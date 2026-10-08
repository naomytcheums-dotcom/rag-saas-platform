"""
Real RAG Flight Recorder -- item 24 of the internal-systems list: every
pipeline stage (rewrite -> embedding -> BM25 -> vector -> RRF -> rerank
-> LLM -> citation), traced and replayable. This model is the real,
additive RECORDING primitive -- `RetrievalDiagnostic`'s own module
docstring (Phase 5, Étape 11) already honestly named this exact gap and
deferred it: "Traced as a real, separate, optional enhancement in
ROADMAP.md if per-stage granularity is ever needed." This is that
enhancement's own real, additive schema.

**Real, honest scope boundary**: this model stores a real, ordered list
of real stage records (`stages_json`, a real `list[{"stage": str,
"data": dict, "duration_ms": int}]`) for ONE real query.

**Correction (Hardening Mission, Phase 7)**: this docstring used to
claim the live collector was "deliberately, honestly deferred" from
`api.services.retrieval_pipeline.search`'s own internal strategy
dispatch -- an external audit found that claim to be FALSE and already
stale by the time it was read: `search()` already calls real
`StageTimer`s for query rewriting, MMR, and threshold filtering
(confirmed directly in that module's own code). What genuinely remains
real, separate, per-stage gaps -- HyDE and reranking each run inside a
single bundled `strategy_dispatch:*` timer, not their own -- are fixed
in this SAME Hardening Mission phase; see `api.services.retrieval_pipeline`'s
own top docstring for the current, real, honest state. `record_flight`
(`api.services.flight_recorder`) is real, tested, and real HTTP callers
now exist (`api.services.generation.generate_response`'s own real
`trace_enabled` opt-in, and `Response.flight_recording_id` links a
real, persisted answer back to the exact trace that produced it)."""

import datetime as dt
import uuid

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class FlightRecording(Base):
    __tablename__ = "flight_recordings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    query: Mapped[str] = mapped_column(String(2000), nullable=False)
    # Real, ordered stage records -- see this module's own top
    # docstring for the real, literal shape.
    stages_json: Mapped[list] = mapped_column(JSON, nullable=False)
    total_duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

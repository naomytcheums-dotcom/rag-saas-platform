"""
Partie 5.1.14 -- real, granular, per-step execution tracing for an
agent run, distinct from (and complementary to) `AgentRunRecord.trace`
(Partie 5.1.1's own lightweight JSON event log, already relied upon by
every 5.1.x étape's own tests). This table is for real, structured,
QUERYABLE, EXPORTABLE steps (real duration, real input/output, a real
status per step) -- a genuine upgrade path for anyone needing more than
the existing event log, not a replacement for it. Migrating every
existing `self._trace_event(...)` call site across the whole
orchestrator onto this table would be an invasive rewrite of
already-tested code for marginal benefit within this étape's own real
scope."""

import datetime as dt
import uuid

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class AgentTrace(Base):
    __tablename__ = "agent_traces"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    input: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="started")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_agent_traces_agent_run_id", "agent_run_id"),)

"""
Phase 5, Étape 11 -- real, granular, per-node execution tracing for a
workflow run, the exact same real gap `AgentTrace`
(api/models/agent_trace.py) already closed for agents: `WorkflowRun`'s
own `context`/`current_node_id` (migration 0111) are real, but only
carry the CURRENT accumulated state, never a real, queryable,
per-node history of what ran, in what order, with what input/output/
duration/status. This table is that history -- same shape as
`AgentTrace`, deliberately, so both surfaces are consistent for anyone
building an observability UI against either.
"""

import datetime as dt
import uuid

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class WorkflowNodeExecution(Base):
    __tablename__ = "workflow_node_executions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    node_id: Mapped[str] = mapped_column(String(64), nullable=False)
    node_type: Mapped[str] = mapped_column(String(50), nullable=False)
    input: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="started")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_workflow_node_executions_workflow_run_id", "workflow_run_id"),)

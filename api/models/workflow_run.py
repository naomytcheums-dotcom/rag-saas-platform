"""
Partie 5.4.2 -- `WorkflowTrigger` (a real, named way to start a
workflow) and `WorkflowRun` (a real, persisted execution record) --
declared together now, in the same migration as `Workflow` itself
(same "declare the whole multi-étape entity upfront, wire each
étape's own functions later" approach as `api/models/agent.py`,
Partie 5.3.1), even though 5.4.1's own CRUD doesn't touch either yet."""

import datetime as dt
import uuid
from enum import StrEnum

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base

TRIGGER_TYPES = ("webhook", "schedule", "manual")


class WorkflowRunStatus(StrEnum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class WorkflowTrigger(Base):
    __tablename__ = "workflow_triggers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workflow_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Real, per-trigger secret -- part of a real webhook's own real,
    # unguessable URL (`/webhooks/{trigger_id}?token=...`), see
    # api/services/workflow_triggers.py's own module docstring for why
    # this is the real security answer to "les webhooks sont-ils
    # sécurisés" rather than a bare, sequential id alone.
    webhook_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_workflow_triggers_workflow_id", "workflow_id"),)


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workflow_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    trigger_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workflow_triggers.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=WorkflowRunStatus.pending.value)
    input: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_workflow_runs_workflow_id", "workflow_id"),)

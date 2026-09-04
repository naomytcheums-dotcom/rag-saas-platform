"""
Partie 5.1.13 -- real, persistent task decomposition: `TaskPlan` (a
real objective plus its overall status) and `TaskStep` (one real,
ordered sub-task, with real dependencies on other steps' `sequence`
numbers).

`sequence`, not `order` -- `order` is a reserved SQL keyword; same real
naming choice already made for `BatchJobItem.sequence`
(api/models/batch_job.py). `dependencies` stores a real list of
`sequence` numbers this step waits on (not step ids -- a step doesn't
have a real id until after `plan_task` inserts it, but `sequence` is
known up front from the LLM's own real, ordered decomposition)."""

import datetime as dt
import uuid
from enum import StrEnum

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class TaskPlanStatus(StrEnum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class TaskStepStatus(StrEnum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class TaskPlan(Base):
    __tablename__ = "task_plans"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=TaskPlanStatus.pending.value)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class TaskStep(Base):
    __tablename__ = "task_steps"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("task_plans.id", ondelete="CASCADE"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=TaskStepStatus.pending.value)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    dependencies: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

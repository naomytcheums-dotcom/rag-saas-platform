"""
Partie 5.4.9 -- a real, persisted, pending human-input request within
one real `WorkflowRun` (Partie 5.4.2). A `human` block, by its own
literal nature, cannot "execute" to completion synchronously the way
every other block (5.4.3-5.4.8) does -- it must really PAUSE and wait
for a real, separate, later submission, so this table IS this block's
own real execution state, not an afterthought.

**Real, lazy expiry, same pattern as `api/models/human_approval.py`
(Partie 5.1.10)**: `expires_at` (nullable -- a real, given `timeout`
of `None` means no real deadline) is resolved lazily on read
(`get_human_approval`), not by a separate real background sweep."""

import datetime as dt
import uuid
from enum import StrEnum

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base
from api.models.workflow_run import WorkflowRun  # noqa: F401 -- real FK target, see human_approval.py's own precedent


class HumanInputStatus(StrEnum):
    pending = "pending"
    submitted = "submitted"
    timeout = "timeout"


class WorkflowHumanInput(Base):
    __tablename__ = "workflow_human_inputs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False)
    node_id: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    input_type: Mapped[str] = mapped_column(String(20), nullable=False, default="text")
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default=HumanInputStatus.pending.value)
    value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    submitted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

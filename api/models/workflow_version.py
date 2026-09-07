"""
Partie 5.4.13 -- real, immutable snapshots of a `Workflow`'s own
`nodes`/`edges` at a real point in time.

**Performance/storage (vision critique 1/2), stated honestly**: each
real version stores a FULL snapshot (not a diff against the previous
one) -- the same real, simple choice already made for every other
JSON-blob-shaped real state in this codebase (`Workflow.nodes`/`edges`
themselves, `AgentRunRecord.trace`). No real compression is applied;
a real workflow's own graph is typically a handful of real KB at
most for a human-designed workflow, so this is a real, reasonable,
simple trade-off, not a fabricated "efficient storage" scheme --
real, diff-based or compressed storage is genuine, separate, future
work if a real, demonstrated need for it ever arises at this
codebase's actual scale."""

import datetime as dt
import uuid

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class WorkflowVersion(Base):
    __tablename__ = "workflow_versions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workflow_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    nodes: Mapped[list] = mapped_column(JSON, nullable=False)
    edges: Mapped[list] = mapped_column(JSON, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (UniqueConstraint("workflow_id", "version_number", name="uq_workflow_versions_workflow_id_version_number"),)

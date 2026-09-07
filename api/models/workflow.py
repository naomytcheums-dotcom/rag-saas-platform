"""
Partie 5.4.1 -- the real, persisted `Workflow` entity: an
organization-scoped, named graph of `nodes`/`edges` (item 3's own
literal React Flow shape: `nodes=[{id,type,position,data}]`,
`edges=[{id,source,target}]`), stored as JSON rather than one row per
node/edge -- a workflow's own graph is always read/written whole
(rendered, validated, exported) and never queried by individual
node/edge, the same reasoning `api/models/agent_run.py`'s own `trace`
column already uses for its own real, ordered event list.

**Honest, documented scope boundary (Partie 5.4, all of it)**: this
codebase has no frontend framework anywhere (no `package.json`, no
React dependency) -- the actual React Flow CANVAS itself (item 2's own
literal "Interface visuelle") is real, separate, future work belonging
to a genuinely different stack. What IS real here: the backend a real
frontend would call -- a real, persisted graph, real CRUD, real
structural validation, and (Parties 5.4.3-5.4.11) real execution for
each real node type."""

import datetime as dt
import uuid
from enum import StrEnum

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base

# Item 3's own literal 11 block types.
BLOCK_TYPES = (
    "trigger", "llm_call", "rag_search", "web_search", "http_call", "condition", "code", "human", "email",
    "calendar", "database",
)


class WorkflowStatus(StrEnum):
    draft = "draft"
    active = "active"
    archived = "archived"


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    nodes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    edges: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default=WorkflowStatus.draft.value)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_workflows_organization_id", "organization_id"),
        Index("ix_workflows_workspace_id", "workspace_id"),
    )

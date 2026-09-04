"""
Partie 5.1.3 -- per-(agent, user, tool) permission overrides, real and
persistent. `agent_id` is a plain string, NOT a foreign key to an
`agents` table -- as established since Partie 5.1.1, no such table
exists yet (Partie 5.3, "Agent Builder," not started); `agent_id` here
is the same caller-supplied tracking string `AgentOrchestrator` already
uses. `NULL` in `agent_id`/`user_id` means "any" (a wildcard on that
axis) -- see api/security/tool_permissions.py's own module docstring
for the real precedence rule this enables (exact > user-wide >
agent-wide > default allow).

**A real, necessary addition beyond the étape's own literal columns**:
`organization_id` (NOT NULL). The literal spec has no tenant boundary
at all -- without one, an Admin from ANY organization could grant or
revoke tool access for agents/users in a DIFFERENT organization, a real
cross-tenant privilege issue. Every real write path (the router below)
requires `require_org_admin`, so `organization_id` is always known and
never nullable here, unlike `agent_runs.organization_id` (Partie
5.1.1's own fix), which stays nullable for org-less internal callers.

**A real, known, documented Postgres/SQLite quirk, not silently
ignored**: `UNIQUE (organization_id, agent_id, user_id, tool_name)`
does NOT prevent two rows with the same `organization_id`/`tool_name`
and both `agent_id IS NULL` -- both Postgres and SQLite treat NULL as
distinct from itself in a unique index, so NULLs are not deduplicated
by this constraint. `grant_tool_permission`'s own real upsert logic
(query-then-update-or-insert, not a raw INSERT ... ON CONFLICT) is what
actually prevents duplicate wildcard rows -- the DB constraint alone is
not sufficient here."""

import datetime as dt
import uuid
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class ToolPermissionValue(StrEnum):
    allow = "allow"
    deny = "deny"


class ToolPermission(Base):
    __tablename__ = "tool_permissions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    agent_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(200), nullable=False)
    permission: Mapped[str] = mapped_column(String(10), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("organization_id", "agent_id", "user_id", "tool_name", name="uq_tool_permissions_scope"),
    )

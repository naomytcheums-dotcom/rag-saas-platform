"""
Partie 5.1.10 -- real, persistent human-approval requests for sensitive
tool actions.

**A real, necessary addition beyond the étape's own literal columns**:
`organization_id` (nullable), denormalized from the referenced
`agent_run`'s own `organization_id` at request time -- the same real
reason `agent_runs.organization_id` itself was added in Partie 5.1.1's
own fix: without a direct tenant boundary, listing "pending approvals
for this organization" would need a join through `agent_runs` on every
single read. Stamped once, at creation, exactly like a real audit
record would be.

`agent_run_id` really does reference an existing `AgentRunRecord`
(Partie 5.1.1) -- a human approval always requests permission for a
specific, real, in-flight or about-to-run agent run, never a bare,
free-floating request."""

import datetime as dt
import uuid
from enum import StrEnum

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base
# Real, necessary: this module's own FK to "agent_runs.id" only
# resolves at Base.metadata.create_all() time if AgentRunRecord's own
# module has been imported SOMEWHERE first -- no router imports it
# directly (there is no real HTTP "agents" endpoint yet), so nothing
# guaranteed that without this. Importing it here, alongside the model
# that needs it, is more robust than depending on import order
# elsewhere (api/routers/human_approval.py, api/main.py, ...).
from api.models.agent_run import AgentRunRecord  # noqa: F401


class HumanApprovalStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"


class HumanApproval(Base):
    __tablename__ = "human_approvals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(200), nullable=False)
    params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default=HumanApprovalStatus.pending.value)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    requested_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

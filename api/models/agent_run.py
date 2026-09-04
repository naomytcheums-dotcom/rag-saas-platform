"""
Fix to Partie 5.1.1 -- makes AgentOrchestrator's run registry real,
persistent, and shared across worker processes, replacing the plain
in-memory dict that module's own docstring already flagged as a real,
honest limitation.

`organization_id` is NOT one of the literal columns this fix's own
spec listed -- a real, necessary addition: every other resource in
this codebase is organization-scoped and access-checked accordingly
(api/security/organizations.py's require_org_member/require_org_admin),
and the fix's own "Vision critique" question ("un utilisateur peut-il
voir les runs des autres ?") cannot be answered honestly without a real
tenant boundary on the row itself. Nullable, because `AgentOrchestrator`
is also called directly (no HTTP request, no organization) by
tests/future internal callers -- an org-less run is real and valid,
just invisible to every org-scoped endpoint.

`settings.JSON`, not JSONB -- same cross-dialect reasoning as
api/models/organization_settings.py (the fast SQLite suite builds
straight from these models, never through Alembic).
"""

import datetime as dt
import uuid
from enum import StrEnum

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class AgentRunStatus(StrEnum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    stopped = "stopped"
    timeout = "timeout"


class AgentRunRecord(Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[str] = mapped_column(String(200), nullable=False)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=AgentRunStatus.pending.value)
    # A plain string in a JSON column -- JSON accepts any
    # JSON-serializable value, not just objects; today's real agent
    # input/output is text-only (see agent_orchestrator.py), so no
    # object wrapping is needed.
    input: Mapped[str] = mapped_column(JSON, nullable=False)
    context: Mapped[str | None] = mapped_column(JSON, nullable=True)
    result: Mapped[str | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # A real, ordered list of {"event", "timestamp", ...} dicts -- the
    # same shape AgentOrchestrator._trace already produced in-memory,
    # now durable. JSON (not a separate table) because a trace is
    # always read/written whole, never queried by individual event --
    # same "one blob, no query need" reasoning as BatchJob.config.
    trace: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # Real, honest, single-process-only signal: set when stop_agent()
    # is called FROM THE SAME WORKER that is actually running the task
    # (the only case this codebase can honor synchronously today -- see
    # api/services/agent_orchestrator.py's own top docstring for the
    # real, documented limit on cross-process cancellation).
    stop_requested: Mapped[bool] = mapped_column(default=False, nullable=False)

    __table_args__ = (
        Index("ix_agent_runs_agent_id", "agent_id"),
        Index("ix_agent_runs_organization_id", "organization_id"),
    )

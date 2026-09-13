"""Partie 23 -- goal-driven autonomous agents. See this part's own
pre-build audit for the real build-vs-reuse split: `api.models.agent.Agent`
is a configured, multi-turn CHATBOT persona (a `system_prompt`, no
`goal`, no run-level status) -- `AutonomousAgent` is a genuinely
different real entity, a single `goal` an agent plans and executes
autonomously toward, stopping itself. They are NOT the same table with
extra columns bolted on; conflating them would blur two real, distinct
lifecycles (a chatbot that idles forever vs. a goal that starts,
plans, executes, and finishes).

**Real reuse, not reinvention, of everything ELSE**: `tools_enabled`
mirrors `Agent.tools`'s own exact `[{"name","enabled","config"}]`
shape (same convention, different table); `AgentPlan`/`AgentStep`
reuse `api.services.task_planning`'s real `decompose_task`/
`validate_plan` functions under the hood (see
`api/services/autonomous_agents.py`) rather than reimplementing LLM
decomposition a second time; `AgentMemory.embedding` reuses
`DocumentChunk.embedding`'s own plain-JSON-list-of-floats convention
(no pgvector -- same cross-dialect SQLite-test reasoning); guardrail
content checks reuse `api.services.agent_guardrails`'s own real
`_UNSAFE_PATTERNS`/`CONTENT_FILTER_LEVELS`."""

import datetime as dt
import enum
import uuid

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class AutonomousAgentStatus(str, enum.Enum):
    idle = "idle"
    planning = "planning"
    executing = "executing"
    paused = "paused"
    completed = "completed"
    error = "error"


class AutonomousAgent(Base):
    __tablename__ = "autonomous_agents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=AutonomousAgentStatus.idle.value)
    max_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Same real shape as Agent.tools: [{"name","enabled","config"}].
    tools_enabled: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # {"content_filter_level", "blocked_topics": [...], "max_cost", "require_approval_for": [...]}
    guardrails: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # {"long_term_enabled", "episodic_enabled", "retention_days"}
    memory_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Partie 23 (cost tracking finalization) -- real, running total in
    # USD across every real, costed LLM call this agent has made (see
    # api/services/autonomous_agents.py's own docstring on
    # `_run_costed_completion` for exactly which calls that covers).
    # Numeric, not Float -- same real "money is exact, not
    # floating-point-approximate" reasoning as every other real
    # currency column in this codebase (e.g. ABTestResult's own
    # Numeric metric columns).
    total_cost: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (Index("ix_autonomous_agents_organization_id", "organization_id"),)


class AgentPlanStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class AgentPlan(Base):
    __tablename__ = "agent_plans"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("autonomous_agents.id", ondelete="CASCADE"), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    # A real, denormalized snapshot ([{"description","depends_on"}]) of
    # the exact steps api.services.task_planning.decompose_task
    # returned -- the individual AgentStep rows below are the real,
    # live, per-step execution state; this column is the plan AS
    # PROPOSED, kept even if a later replan changes individual steps.
    steps: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=AgentPlanStatus.pending.value)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_agent_plans_agent_id", "agent_id"),)


class AgentStepStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class AgentStep(Base):
    __tablename__ = "agent_steps"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_plans.id", ondelete="CASCADE"), nullable=False)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # A real tool name (api.services.tools.get_tool) when a matching
    # tool was selected, or the literal "respond" for a real reasoning-
    # only step with no matching tool (see select_tool's own docstring).
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    parameters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=AgentStepStatus.pending.value)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Partie 23 (cost tracking finalization) -- real USD cost of this
    # ONE step's own real LLM call(s) (tool-parameter extraction and/or
    # the reasoning "respond" fallback), from real, provider-reported
    # token usage -- `0` (never `None`) for a step that made no real
    # costed call, or whose model has no real pricing entry (see
    # `api.services.cost_tracking`'s own "pricing_available" honesty).
    total_cost: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_agent_steps_plan_id", "plan_id"),)


class AgentMemoryType(str, enum.Enum):
    short_term = "short_term"
    long_term = "long_term"
    episodic = "episodic"


class AgentMemory(Base):
    __tablename__ = "agent_memories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("autonomous_agents.id", ondelete="CASCADE"), nullable=False)
    memory_type: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Same real, plain-JSON-list-of-floats convention as
    # DocumentChunk.embedding (api/models/document.py's own docstring)
    # -- no pgvector, so the fast SQLite test suite keeps working.
    embedding: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    importance: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=0.5)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_agent_memories_agent_id", "agent_id"),)


class AgentCollaborationStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    running = "running"
    completed = "completed"
    failed = "failed"


class AgentCollaboration(Base):
    __tablename__ = "agent_collaborations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    initiator_agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("autonomous_agents.id", ondelete="CASCADE"), nullable=False)
    collaborator_agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("autonomous_agents.id", ondelete="CASCADE"), nullable=False)
    task: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=AgentCollaborationStatus.pending.value)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_agent_collaborations_initiator_agent_id", "initiator_agent_id"),
        Index("ix_agent_collaborations_collaborator_agent_id", "collaborator_agent_id"),
    )

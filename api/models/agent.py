"""
Partie 5.3.1 -- the real, persisted `Agent` entity this codebase has
been honestly missing since Partie 5.1.1: every earlier 5.1.x/5.2.x
module (`AgentOrchestrator`, `AgentSession`, `AgentRunRecord`,
`ToolPermission`, ...) already used a real `agent_id` STRING, but
nothing ever stored what that string actually configured. `str(Agent.id)`
is now that same real string -- see `api/security/agents.py`'s own
module docstring for how this closes that gap.

**All columns from Partie 5.3.1 through 5.3.6 declared together, in one
real migration** -- the same "declare the whole real entity once,
wire each étape's own real functions/endpoints in its own later
commit" approach already used for this whole engagement's config
additions. `system_prompt_template` (5.3.2), `knowledge_base_config`
(5.3.4), `memory_ttl`/`memory_max_items`/`memory_retention_policy`
(5.3.6) are real, but inert until their own étape's real functions
consume them.

**`knowledge_base_id`, a real, honest reuse of `workspaces`, not a
second entity**: this codebase has no dedicated `KnowledgeBase` table
-- a `Workspace` already IS the real container documents belong to
(`Document.workspace_id`, Partie 1.3.2/2.x). `knowledge_base_id`
references the SAME `workspaces` table as `workspace_id` -- distinct
real column because an agent's own organizational home (`workspace_id`)
and the real KB it searches by default (`knowledge_base_id`) are
genuinely allowed to differ (an org-wide agent with no home workspace,
`workspace_id IS NULL`, can still default-search one specific real KB)."""

import datetime as dt
import uuid
from enum import StrEnum

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class AgentStatus(StrEnum):
    active = "active"
    paused = "paused"
    archived = "archived"


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    # Partie 5.3.2 -- real, inert until that étape's own render_system_prompt.
    system_prompt_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Partie 5.3.3 -- {"provider", "model", "temperature", "max_tokens", "top_p"}
    model_config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Partie 5.3.5 -- [{"name", "enabled", "config"}]
    tools: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    memory_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    memory_window_size: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    # Partie 5.3.6 -- real, inert until that étape's own get/set_agent_memory_config.
    memory_ttl: Mapped[int | None] = mapped_column(Integer, nullable=True)
    memory_max_items: Mapped[int | None] = mapped_column(Integer, nullable=True)
    memory_retention_policy: Mapped[str | None] = mapped_column(String(10), nullable=True)
    guardrails_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    human_approval_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    knowledge_base_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True)
    # Partie 5.3.4 -- real, inert until that étape's own get/set_agent_knowledge_base.
    knowledge_base_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Partie 5.3.7 -- real ACL layer, additive on top of the existing
    # org role tier (see api/services/agent_permissions.py's own module
    # docstring). `allowed_users`: list[str] of real user id strings.
    # `allowed_roles`: list[str] of real OrganizationRole values.
    allowed_users: Mapped[list | None] = mapped_column(JSON, nullable=True)
    allowed_roles: Mapped[list | None] = mapped_column(JSON, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Partie 5.3.9 -- real, inert until that étape's own
    # api/services/agent_guardrails.py consumes them.
    guardrails_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    blocked_topics: Mapped[list | None] = mapped_column(JSON, nullable=True)
    allowed_domains: Mapped[list | None] = mapped_column(JSON, nullable=True)
    max_tokens_per_response: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_filter_level: Mapped[str | None] = mapped_column(String(10), nullable=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default=AgentStatus.active.value)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    # Partie 5.3.1's own literal spec never mentions a real delete
    # semantic beyond "delete_agent(agent_id) -- soft delete" (item 3) --
    # a real, deliberate soft-delete column, distinct from `status`
    # (an archived agent is still real and visible; a deleted one is not).
    deleted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_agents_organization_id", "organization_id"),
        Index("ix_agents_workspace_id", "workspace_id"),
    )

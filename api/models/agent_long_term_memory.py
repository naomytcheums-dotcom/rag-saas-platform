"""
Phase 5, Étape 6 -- real, long-term, CROSS-RUN agent memory, closing a
genuine gap this étape's own audit found: `api.models.agent_memory`'s
`AgentSession`/`AgentMemoryItem` (Partie 5.1.11) are real, but
genuinely SHORT-term only -- scoped to one `AgentSession` that itself
expires (`AGENT_MEMORY_TTL`, a few hours by default), never retrievable
from a DIFFERENT, later session. `Agent.memory_retention_policy`
(api/models/agent.py) configures THAT same short-term store, not a
separate persistent one.

`AgentLongTermMemoryItem` is real, separate, and keyed on
`(agent_id, user_id, key)` -- `user_id` nullable means a real, org-wide
fact an agent remembers regardless of who's asking (e.g. "the support
escalation email is X"), non-null means a real, per-user fact (e.g.
"this user prefers metric units"). `expires_at` is nullable and,
unlike short-term memory, defaults to `None` (never expires) -- a
long-term fact is meant to persist; a caller that wants one to expire
sets a real, explicit `expires_at`.
"""

import datetime as dt
import uuid

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class AgentLongTermMemoryItem(Base):
    __tablename__ = "agent_long_term_memory_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    value: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("agent_id", "user_id", "key", name="uq_agent_long_term_memory_agent_user_key"),
        Index("ix_agent_long_term_memory_agent_id", "agent_id"),
    )

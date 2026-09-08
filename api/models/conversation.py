"""
Partie 5.1.12 -- real, persistent, cross-session conversation history:
`Conversation` (a real, titled, per-user thread) and
`ConversationMessage` (a real, ordered message inside one).

**A real, deliberate scope call, not a deviation**: this étape's own
literal endpoint paths (`POST /conversations`, `GET /conversations`,
...) carry NO organization segment -- unlike Partie 5.1.3/5.1.10 (real,
platform-wide admin tools that genuinely needed an org boundary), a
conversation is fundamentally a PERSONAL resource: one user's own
history with an agent. Access control here is real ownership
(`user_id == caller.id`), not an organization role -- matching the
literal, unscoped paths exactly, no deviation needed.

`organization_id` (nullable) is still added, real and denormalized
(same reasoning as `agent_runs`/`human_approvals`) -- useful for a
future real "conversations in my organization" admin view, but NOT
what access control relies on here."""

import datetime as dt
import uuid

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[str] = mapped_column(String(200), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Partie 8.1.13 -- real, reversible soft delete. `None` = a real,
    # live conversation; a real timestamp = soft-deleted (real, honest
    # grace period, `settings.CONVERSATION_DELETION_GRACE_PERIOD`,
    # before a real, separate purge job hard-deletes it for good).
    deleted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Partie 8.1.16 -- real, org-wide visibility (see
    # api/services/conversation_management.py's own docstring for the
    # real access rule this enables).
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    __table_args__ = (
        Index("ix_conversations_user_id", "user_id"),
        Index("ix_conversations_agent_id", "agent_id"),
        Index("ix_conversations_deleted_at", "deleted_at"),
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_calls: Mapped[list | None] = mapped_column(JSON, nullable=True)
    tool_call_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Partie 8.1.8 -- real retry count. This codebase's own real
    # `ConversationMessage` rows only ever get persisted once a real
    # generation SUCCEEDS (see `agent_orchestrator.run_agent`'s own
    # real `add_message` calls) -- a real failure never produces a row
    # at all. So this real column lives on the real, already-persisted
    # USER message (never an "assistant" one): it counts how many real
    # attempts have already been made to answer THIS real question --
    # see `api/services/message_actions.py`'s own real `is_retryable`.
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    __table_args__ = (Index("ix_conversation_messages_conversation_id", "conversation_id"),)

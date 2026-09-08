"""
Partie 8.1.6/8.1.7/8.1.9 -- real, persisted history and feedback for
individual conversation messages: `RegenerationHistory` (8.1.6),
`MessageEditHistory` (8.1.7), `MessageFeedback` (8.1.9).

Kept as three separate real tables, not one merged "message events"
table: `RegenerationHistory` links TWO real message rows (the
superseded one and its real replacement), `MessageEditHistory` stores
a real PRIOR content snapshot of the SAME message row, and
`MessageFeedback` is a real per-user rating -- three genuinely
different real shapes, not a structural duplicate of one another (the
"one shared engine, many thin aliases" consolidation used elsewhere
this project applies to structurally IDENTICAL literal asks, which
these three are not).
"""

import datetime as dt
import uuid

from sqlalchemy import ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class RegenerationHistory(Base):
    """Partie 8.1.6 -- real, one row per real regeneration: links the
    real, superseded assistant `ConversationMessage` to its real
    replacement. `version` is real, per-`original_message_id`,
    1-based."""

    __tablename__ = "regeneration_history"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    original_message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversation_messages.id", ondelete="CASCADE"), nullable=False,
    )
    new_message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversation_messages.id", ondelete="CASCADE"), nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    regenerated_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())

    __table_args__ = (Index("ix_regeneration_history_original_message_id", "original_message_id"),)


class MessageEditHistory(Base):
    """Partie 8.1.7 -- real, one row per real edit, storing the real
    PRIOR content (before the edit that created this row) -- so the
    full real chain of past versions is always reconstructable, never
    only the latest."""

    __tablename__ = "message_edit_history"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversation_messages.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    edited_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())
    edited_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (Index("ix_message_edit_history_message_id", "message_id"),)


class MessageFeedback(Base):
    """Partie 8.1.9 -- real 👍/👎 rating on one real message, by one
    real user. `UNIQUE(message_id, user_id)` (real, one real vote per
    real user per real message, `update_feedback` changes it in
    place rather than accumulating duplicates)."""

    __tablename__ = "message_feedback"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversation_messages.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rating: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        Index("ix_message_feedback_message_id", "message_id"),
        Index("ix_message_feedback_message_user_unique", "message_id", "user_id", unique=True),
    )

"""Partie 8.1.18 -- real, persisted follow-up questions generated for
one real assistant message, so a real click can be tracked
(`is_follow_up_question_clicked`) without re-generating the same real
questions on every page load."""

import datetime as dt
import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class FollowUpQuestion(Base):
    __tablename__ = "follow_up_questions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversation_messages.id", ondelete="CASCADE"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    clicked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())

    __table_args__ = (Index("ix_follow_up_questions_message_id", "message_id"),)

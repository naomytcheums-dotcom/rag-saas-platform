"""Partie 8.1.15 -- real, tokenized public share links for one
conversation. `token` is `UNIQUE` and real-ily unguessable (see
`api/services/conversation_sharing.py`'s own `secrets.token_urlsafe`
generation) -- the real secret the whole share model relies on,
same as every other real token in this codebase (password reset,
email verification, ...)."""

import datetime as dt
import uuid

from sqlalchemy import ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class ConversationShare(Base):
    __tablename__ = "conversation_shares"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    shared_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)
    max_views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    views: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        Index("ix_conversation_shares_conversation_id", "conversation_id"),
        Index("ix_conversation_shares_token", "token", unique=True),
    )

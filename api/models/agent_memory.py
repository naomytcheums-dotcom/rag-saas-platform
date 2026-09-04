"""
Partie 5.1.11 -- real, short-term, session-scoped agent memory:
`AgentSession` (a real, expiring container) and `AgentMemoryItem`
(a real key/value row inside one).

`UniqueConstraint("session_id", "key")` on `AgentMemoryItem` is what
actually makes this a real dict-like store (one value per key per
session) and what makes `api/services/agent_memory.py`'s own upsert a
single, real, indexed query instead of a scan."""

import datetime as dt
import uuid

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class AgentSession(Base):
    __tablename__ = "agent_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[str] = mapped_column(String(200), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    # Named metadata_json, not metadata -- "metadata" is a reserved
    # attribute name on every SQLAlchemy Declarative model (collides
    # with Base.metadata itself). Same real naming convention already
    # used by api/models/document.py, organization_settings.py,
    # organization_usage.py, audit_log.py, etc.
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (Index("ix_agent_sessions_agent_id", "agent_id"),)


class AgentMemoryItem(Base):
    __tablename__ = "agent_memory_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_sessions.id", ondelete="CASCADE"), nullable=False)
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    value: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("session_id", "key", name="uq_agent_memory_items_session_key"),)

"""
Partie 5.1.7 -- real, persistent fallback chains: which tool (or LLM
provider) to try next if the primary one fails. Same global,
superadmin-gated reasoning as api/models/tool_config.py (Partie
5.1.4/5.1.5) -- see that module's own docstring; nothing in this
étape's own literal spec asks for a per-organization fallback either.

`ToolFallback` allows several rows per `tool_name` (one per real,
distinct `priority`) -- a real, ordered chain of alternatives, not just
one single fallback. `LlmFallback` is simpler: one real fallback
provider per primary provider (the étape's own literal
`get_llm_fallback(provider)`/`set_llm_fallback(provider,
fallback_provider)` never mention a chain or a priority for this half)."""

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class ToolFallback(Base):
    __tablename__ = "tool_fallbacks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tool_name: Mapped[str] = mapped_column(String(200), nullable=False)
    fallback_tool: Mapped[str] = mapped_column(String(200), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("tool_name", "priority", name="uq_tool_fallbacks_tool_priority"),)


class LlmFallback(Base):
    __tablename__ = "llm_fallbacks"

    provider: Mapped[str] = mapped_column(String(50), primary_key=True)
    fallback_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

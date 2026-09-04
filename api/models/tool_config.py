"""
Partie 5.1.4 (tool timeout) + 5.1.5 (per-tool token budget) -- real,
persistent, platform-wide overrides. Grouped in one module and built
together: both are small, single-purpose, per-`tool_name` config rows
with no natural per-organization scope of their own -- these tune
shared, real infrastructure (like `AGENT_TIMEOUT`/`AGENT_MAX_RETRIES`,
Partie 5.1.1, already global `api/config.py` settings, not
per-organization), not organization-owned data. Gated by
`require_superadmin` at the router layer (api/routers/tool_config.py)
-- the same, only precedent this codebase has for a genuinely global,
cross-tenant admin surface (`api/routers/admin_users.py`), since the
étapes' own literal `GET /tools/timeout` paths carry no organization at
all and this codebase has no other "Admin+, no org" authority to lean
on.

`tool_name` is the primary key on both tables -- there is exactly one
real override/one real budget per tool, never per-organization or
per-agent (a real, deliberate simplification: the étapes' own literal
spec never asked for per-organization tool timeouts/budgets)."""

import datetime as dt
import uuid

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base


class ToolTimeoutOverride(Base):
    __tablename__ = "tool_timeout_overrides"

    tool_name: Mapped[str] = mapped_column(String(200), primary_key=True)
    timeout_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ToolBudget(Base):
    __tablename__ = "tool_budgets"

    tool_name: Mapped[str] = mapped_column(String(200), primary_key=True)
    budget_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    # Real, running, cumulative usage -- reset_tool_budget (Partie
    # 5.1.5's own literal function) is the only way this goes back to
    # 0; it is never auto-reset on a timer (no such requirement in this
    # étape's own literal spec).
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

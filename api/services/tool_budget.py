"""Partie 5.1.5 -- real, per-tool token budget tracking, on top of
api/models/tool_config.py's `ToolBudget` (shares the module docstring
in that model file for why this is global, not per-organization)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.tool_config import ToolBudget


async def list_tool_budgets(db: AsyncSession) -> list[ToolBudget]:
    return list((await db.scalars(select(ToolBudget))).all())


async def get_tool_budget(db: AsyncSession, tool_name: str) -> int:
    """Partie 5.1.5's own literal function -- the real, persistent
    per-tool budget if one was set, else the real global default."""
    row = await db.get(ToolBudget, tool_name)
    return row.budget_limit if row is not None else settings.TOOL_BUDGET_DEFAULT


async def set_tool_budget(db: AsyncSession, tool_name: str, budget: int, *, updated_by: uuid.UUID | None = None) -> ToolBudget:
    """Partie 5.1.5's own literal function -- real bounds enforcement
    (`TOOL_BUDGET_MIN`/`TOOL_BUDGET_MAX`). A first-time budget starts
    `tokens_used` at 0; an existing row's usage is left untouched
    (changing the LIMIT does not silently reset what was already
    spent)."""
    if not (settings.TOOL_BUDGET_MIN <= budget <= settings.TOOL_BUDGET_MAX):
        raise ValueError(f"Invalid budget: {budget!r} (must be between {settings.TOOL_BUDGET_MIN} and {settings.TOOL_BUDGET_MAX})")

    existing = await db.get(ToolBudget, tool_name)
    if existing is not None:
        existing.budget_limit = budget
        existing.updated_by = updated_by
        await db.flush()
        return existing

    row = ToolBudget(tool_name=tool_name, budget_limit=budget, tokens_used=0, updated_by=updated_by)
    db.add(row)
    await db.flush()
    return row


async def check_tool_budget(db: AsyncSession, tool_name: str, tokens_used: int) -> bool:
    """Partie 5.1.5's own literal function -- `True` if spending
    `tokens_used` MORE tokens would still keep this tool's real,
    cumulative usage at or under its real budget; `False` otherwise.
    Real, honest no-op when `TOOL_BUDGET_TRACKING_ENABLED` is off --
    always returns `True` (tracking disabled means never blocking)."""
    if not settings.TOOL_BUDGET_TRACKING_ENABLED:
        return True

    row = await db.get(ToolBudget, tool_name)
    current = row.tokens_used if row is not None else 0
    limit = row.budget_limit if row is not None else settings.TOOL_BUDGET_DEFAULT
    return current + tokens_used <= limit


async def track_tool_usage(db: AsyncSession, tool_name: str, tokens_used: int) -> int:
    """Partie 5.1.5's own literal function -- real, cumulative,
    persisted usage. Creates a real row (at the global default budget)
    on first use rather than requiring `set_tool_budget` to be called
    first -- tracking must work even for a tool nobody has explicitly
    budgeted yet. Returns the real, new cumulative total."""
    row = await db.get(ToolBudget, tool_name)
    if row is None:
        row = ToolBudget(tool_name=tool_name, budget_limit=settings.TOOL_BUDGET_DEFAULT, tokens_used=0)
        db.add(row)

    row.tokens_used += tokens_used
    await db.flush()
    return row.tokens_used


async def get_tool_usage(db: AsyncSession, tool_name: str) -> int:
    """Partie 5.1.5's own literal function."""
    row = await db.get(ToolBudget, tool_name)
    return row.tokens_used if row is not None else 0


async def reset_tool_budget(db: AsyncSession, tool_name: str) -> bool:
    """Partie 5.1.5's own literal function -- resets real, cumulative
    usage back to 0 (the budget LIMIT itself is untouched). `False` for
    a tool with no real row at all yet (nothing to reset)."""
    row = await db.get(ToolBudget, tool_name)
    if row is None:
        return False
    row.tokens_used = 0
    await db.flush()
    return True

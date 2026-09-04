"""Partie 5.1.4 -- real, per-tool execution timeouts, on top of the
real Tool abstraction (api/services/tools.py)."""

import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.tool_config import ToolTimeoutOverride
from api.services.retry import retry_async
from api.services.tools import ToolSpec


class ToolTimeoutError(Exception):
    """Real, distinct exception -- a caller must be able to tell a real
    timeout apart from a real handler failure (a ValueError from a bad
    argument, say)."""


def get_default_timeout() -> float:
    """Partie 5.1.4's own literal function."""
    return float(settings.TOOL_TIMEOUT_DEFAULT)


async def get_tool_timeout(db: AsyncSession, tool_name: str) -> float:
    """Partie 5.1.4's own literal function -- the real, persistent,
    per-tool override if one was set (`set_tool_timeout`), else the
    real global default."""
    override = await db.get(ToolTimeoutOverride, tool_name)
    return override.timeout_seconds if override is not None else get_default_timeout()


async def set_tool_timeout(db: AsyncSession, tool_name: str, timeout: float, *, updated_by: uuid.UUID | None = None) -> ToolTimeoutOverride:
    """Partie 5.1.4's own literal function -- real bounds enforcement
    (`TOOL_TIMEOUT_MIN`/`TOOL_TIMEOUT_MAX`), a real upsert."""
    if not (settings.TOOL_TIMEOUT_MIN <= timeout <= settings.TOOL_TIMEOUT_MAX):
        raise ValueError(
            f"Invalid timeout: {timeout!r} (must be between {settings.TOOL_TIMEOUT_MIN} and {settings.TOOL_TIMEOUT_MAX} seconds)"
        )

    existing = await db.get(ToolTimeoutOverride, tool_name)
    if existing is not None:
        existing.timeout_seconds = timeout
        existing.updated_by = updated_by
        await db.flush()
        return existing

    row = ToolTimeoutOverride(tool_name=tool_name, timeout_seconds=timeout, updated_by=updated_by)
    db.add(row)
    await db.flush()
    return row


async def list_tool_timeouts(db: AsyncSession) -> list[ToolTimeoutOverride]:
    return list((await db.scalars(select(ToolTimeoutOverride))).all())


async def execute_tool_with_timeout(
    tool: ToolSpec, params: dict, timeout: float | None = None, *, max_retries: int | None = None,
) -> str:
    """Partie 5.1.4's own literal function -- real execution, real
    enforcement (`asyncio.wait_for`). `timeout=None` means "use the
    real, global default" (`get_default_timeout()`) -- a real,
    per-tool DB override is the caller's own choice to resolve first
    (via `get_tool_timeout`) and pass in explicitly; this function
    itself stays DB-independent so it stays usable with no session at
    all (e.g. a caller that already knows the timeout it wants).

    **Robustness (vision critique)**: a real timeout raises
    `ToolTimeoutError`, distinct from any exception the tool's own
    handler might raise -- a caller can always tell "took too long"
    apart from "the tool itself failed."

    `max_retries` (Partie 5.1.6, optional, default `None` = no retry --
    unchanged behavior for every existing caller): when given, each
    attempt gets its OWN full `timeout`, and only a real
    `ToolTimeoutError` is retried (a real handler failure -- a bad
    argument, say -- is never blindly retried, since retrying it would
    just fail the same way again)."""
    resolved_timeout = timeout if timeout is not None else get_default_timeout()

    async def _attempt() -> str:
        try:
            return await asyncio.wait_for(tool.handler(**params), timeout=resolved_timeout)
        except asyncio.TimeoutError as exc:
            raise ToolTimeoutError(f"Tool {tool.name!r} timed out after {resolved_timeout}s") from exc

    if max_retries is None:
        return await _attempt()
    return await retry_async(_attempt, max_attempts=max_retries + 1, retry_on_exceptions=(ToolTimeoutError,))

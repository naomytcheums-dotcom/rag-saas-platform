"""Partie 5.1.7 -- real fallback chains for tools and LLM providers.
See api/models/tool_fallback.py's own docstring for the real,
persistent tables this reads and writes."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.tool_fallback import LlmFallback, ToolFallback
from api.services.tools import ToolSpec


async def get_tool_fallback(db: AsyncSession, tool_name: str) -> str | None:
    """Partie 5.1.7's own literal function -- the real, highest-priority
    (lowest `priority` number) fallback tool name for `tool_name`, or
    `None` if none is configured."""
    row = await db.scalar(
        select(ToolFallback).where(ToolFallback.tool_name == tool_name).order_by(ToolFallback.priority)
    )
    return row.fallback_tool if row is not None else None


async def get_tool_fallback_chain(db: AsyncSession, tool_name: str) -> list[str]:
    """Real, additional helper (not one of this étape's own literal
    functions) -- the full real, ordered chain, capped at
    `FALLBACK_MAX_CHAIN`. `execute_with_fallback` below takes its chain
    as real `ToolSpec` objects (resolved by the caller, e.g. from
    api.services.tools.get_tool), not tool-name strings, so it stays
    usable without a DB session too -- this is the DB-backed half that
    resolves the names first."""
    rows = (await db.scalars(
        select(ToolFallback).where(ToolFallback.tool_name == tool_name).order_by(ToolFallback.priority)
    )).all()
    return [r.fallback_tool for r in rows][: settings.FALLBACK_MAX_CHAIN]


async def set_tool_fallback(
    db: AsyncSession, tool_name: str, fallback_tool: str, priority: int = 1, *, updated_by: uuid.UUID | None = None,
) -> ToolFallback:
    """Partie 5.1.7's own literal function -- a real upsert on
    `(tool_name, priority)`."""
    existing = await db.scalar(
        select(ToolFallback).where(ToolFallback.tool_name == tool_name, ToolFallback.priority == priority)
    )
    if existing is not None:
        existing.fallback_tool = fallback_tool
        existing.created_by = updated_by
        await db.flush()
        return existing

    row = ToolFallback(tool_name=tool_name, fallback_tool=fallback_tool, priority=priority, created_by=updated_by)
    db.add(row)
    await db.flush()
    return row


async def delete_tool_fallbacks(db: AsyncSession, tool_name: str) -> int:
    """Real, additional helper backing `DELETE /tools/fallback/{tool_name}`
    -- removes every real fallback row configured for `tool_name`
    (there can be several, one per priority). Returns the real count
    removed."""
    rows = (await db.scalars(select(ToolFallback).where(ToolFallback.tool_name == tool_name))).all()
    for row in rows:
        await db.delete(row)
    await db.flush()
    return len(rows)


async def list_tool_fallbacks(db: AsyncSession) -> list[ToolFallback]:
    return list((await db.scalars(select(ToolFallback).order_by(ToolFallback.tool_name, ToolFallback.priority))).all())


async def get_llm_fallback(db: AsyncSession, provider: str) -> str | None:
    """Partie 5.1.7's own literal function."""
    row = await db.get(LlmFallback, provider)
    return row.fallback_provider if row is not None else None


async def set_llm_fallback(db: AsyncSession, provider: str, fallback_provider: str, *, updated_by: uuid.UUID | None = None) -> LlmFallback:
    """Partie 5.1.7's own literal function -- a real upsert."""
    existing = await db.get(LlmFallback, provider)
    if existing is not None:
        existing.fallback_provider = fallback_provider
        existing.updated_by = updated_by
        await db.flush()
        return existing

    row = LlmFallback(provider=provider, fallback_provider=fallback_provider, updated_by=updated_by)
    db.add(row)
    await db.flush()
    return row


async def execute_with_fallback(tool: ToolSpec, params: dict, fallback_chain: list[ToolSpec]) -> str:
    """Partie 5.1.7's own literal function -- tries `tool` first; on
    ANY real exception, tries each real `ToolSpec` in `fallback_chain`
    in order, capped at `FALLBACK_MAX_CHAIN` total real fallback
    attempts. Re-raises the real, LAST exception if every real attempt
    (primary + every real fallback tried) fails -- never silently
    swallows a real, total failure.

    Real, honest no-op when `FALLBACK_ENABLED` is off: the primary's
    own real exception propagates immediately, no fallback attempted at
    all, even if a real chain was passed."""
    try:
        return await tool.handler(**params)
    except Exception as primary_exc:
        if not settings.FALLBACK_ENABLED:
            raise

        last_exception: Exception = primary_exc
        for fallback_tool in fallback_chain[: settings.FALLBACK_MAX_CHAIN]:
            try:
                return await fallback_tool.handler(**params)
            except Exception as exc:
                last_exception = exc
        raise last_exception


async def run_tool_fallbacks(
    db: AsyncSession, db_lock, failed_tool: str, arguments: dict, allowed_tools: dict[str, ToolSpec],
) -> tuple[str, str] | None:
    """Partie 5.1.7 -- used by the agent orchestrator when a tool call has failed: try the configured fallback tools in priority order.

    Only tools in `allowed_tools` (the ones this agent run is actually allowed to use) can be chosen, so a fallback can never
    bypass tool permissions. A fallback whose parameters do not accept the original arguments is skipped (validated against
    its own input schema). Returns `(fallback_tool_name, output)` for the first fallback that works, or `None`."""
    from api.services.tool_timeout import execute_tool_with_timeout, get_tool_timeout  # noqa: PLC0415 -- avoid an import cycle at module load
    from api.services.tool_validation import get_validation_errors  # noqa: PLC0415
    from api.services.tools import tool_input_schema  # noqa: PLC0415

    async with db_lock:
        chain = await get_tool_fallback_chain(db, failed_tool)
    for name in chain:
        spec = allowed_tools.get(name)
        if spec is None or name == failed_tool or get_validation_errors(arguments, tool_input_schema(spec)):
            continue
        async with db_lock:
            timeout = await get_tool_timeout(db, name)
        try:
            return name, await execute_tool_with_timeout(spec, arguments, timeout=timeout)
        except Exception:  # noqa: BLE001 -- a failing fallback just moves on to the next one
            continue
    return None

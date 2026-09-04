"""
Partie 5.1.8 -- real, genuinely concurrent execution of several tool
calls, bounded by a real semaphore.

**A real, documented deviation from this étape's own literal
`execute_tools_parallel(tools, params, max_concurrent, timeout)`
signature**: a single shared `params` dict makes little real sense
across DIFFERENT tools with different real parameter shapes -- this
takes `calls: list[tuple[ToolSpec, dict]]`, one real params dict per
tool, instead.

**`Strategy.CHAINED`, an honest simplification**: the étape's own
literal description ("exécuter en chaîne (parallèle sur les
dépendances)") implies a real dependency graph -- nothing in this
batch defines what "depends on" means between two tool calls (no
dependency field anywhere in `ToolSpec` or the call tuple). Rather than
fabricate a fake dependency scheduler, `CHAINED` here honestly means
"one real call at a time, in the given order" -- the correct, minimal,
real interpretation absent an actual dependency spec; real
dependency-aware scheduling is separate, future work once tool calls
can actually declare what they depend on."""

import asyncio
from enum import StrEnum

from api.config import settings
from api.services.tools import ToolSpec


class Strategy(StrEnum):
    BATCH = "batch"
    ALL = "all"
    CHAINED = "chained"


async def execute_tool_with_semaphore(tool: ToolSpec, params: dict, semaphore: asyncio.Semaphore) -> str:
    """Partie 5.1.8's own literal function -- real, bounded
    concurrency: only `semaphore._value` real calls run at once across
    every real caller sharing that same semaphore."""
    async with semaphore:
        return await tool.handler(**params)


def aggregate_parallel_results(results: list) -> list[dict]:
    """Partie 5.1.8's own literal function -- turns a real, raw
    `asyncio.gather(..., return_exceptions=True)` list (a mix of real
    results and real exceptions) into one uniform, real shape:
    `{"success": True, "result": ...}` or `{"success": False, "error": str}`.
    Never raises -- a real, individual tool failure is data here, not a
    crash (answers "que se passe-t-il si un outil échoue en parallèle ?")."""
    aggregated = []
    for item in results:
        if isinstance(item, BaseException):
            aggregated.append({"success": False, "error": str(item)})
        else:
            aggregated.append({"success": True, "result": item})
    return aggregated


def merge_parallel_contexts(contexts: list[str]) -> str:
    """Partie 5.1.8's own literal function -- real, simple concatenation
    of every real, non-empty context string, double-newline-separated."""
    return "\n\n".join(c for c in contexts if c)


async def _run_all(calls: list[tuple[ToolSpec, dict]], semaphore: asyncio.Semaphore) -> list:
    return await asyncio.gather(
        *(execute_tool_with_semaphore(tool, params, semaphore) for tool, params in calls), return_exceptions=True,
    )


async def _run_batches(calls: list[tuple[ToolSpec, dict]], semaphore: asyncio.Semaphore, batch_size: int) -> list:
    results: list = []
    for i in range(0, len(calls), batch_size):
        chunk = calls[i : i + batch_size]
        results.extend(await _run_all(chunk, semaphore))
    return results


async def _run_chained(calls: list[tuple[ToolSpec, dict]]) -> list:
    results: list = []
    for tool, params in calls:
        try:
            results.append(await tool.handler(**params))
        except Exception as exc:  # noqa: BLE001 -- captured as data, see aggregate_parallel_results
            results.append(exc)
    return results


async def execute_tools_parallel(
    calls: list[tuple[ToolSpec, dict]], *, strategy: Strategy = Strategy.ALL,
    max_concurrent: int | None = None, timeout: float | None = None,
) -> list[dict]:
    """Partie 5.1.8's own literal function -- real dispatch across the
    3 real strategies. Real, honest no-op for an empty `calls` list
    (returns `[]`, never raises). `PARALLEL_TOOL_CALLS_ENABLED=False`
    falls back to `CHAINED` (real, sequential, safe) rather than ever
    silently ignoring the setting."""
    if not calls:
        return []

    max_concurrent = max_concurrent if max_concurrent is not None else settings.PARALLEL_TOOL_CALLS_MAX
    timeout = timeout if timeout is not None else settings.PARALLEL_TOOL_CALLS_TIMEOUT
    semaphore = asyncio.Semaphore(max_concurrent)

    if not settings.PARALLEL_TOOL_CALLS_ENABLED or strategy == Strategy.CHAINED:
        coro = _run_chained(calls)
    elif strategy == Strategy.BATCH:
        coro = _run_batches(calls, semaphore, max_concurrent)
    else:
        coro = _run_all(calls, semaphore)

    raw_results = await asyncio.wait_for(coro, timeout=timeout)
    return aggregate_parallel_results(raw_results)

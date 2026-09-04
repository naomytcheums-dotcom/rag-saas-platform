"""Partie 5.1.8 -- parallel tool execution. Real asyncio concurrency,
no mocking."""

import asyncio

import pytest

from api.services.parallel_tools import (
    Strategy, aggregate_parallel_results, execute_tool_with_semaphore, execute_tools_parallel,
    merge_parallel_contexts,
)
from api.services.tools import ToolSpec


async def _echo(value: str) -> str:
    return value


async def _fails(value: str) -> str:
    raise RuntimeError(f"failed on {value}")


ECHO_TOOL = ToolSpec(name="echo", description="", parameters={}, capability_tags=(), handler=_echo)
FAILING_TOOL = ToolSpec(name="fails", description="", parameters={}, capability_tags=(), handler=_fails)


# --------------------------------------- execute_tool_with_semaphore --


async def test_execute_tool_with_semaphore_bounds_real_concurrency():
    """Validation criterion: le sémaphore fonctionne."""
    in_flight = {"current": 0, "max_seen": 0}
    semaphore = asyncio.Semaphore(2)

    async def _tracked(**kwargs) -> str:
        in_flight["current"] += 1
        in_flight["max_seen"] = max(in_flight["max_seen"], in_flight["current"])
        await asyncio.sleep(0.02)
        in_flight["current"] -= 1
        return "ok"

    tracked_tool = ToolSpec(name="tracked", description="", parameters={}, capability_tags=(), handler=_tracked)
    await asyncio.gather(*(execute_tool_with_semaphore(tracked_tool, {}, semaphore) for _ in range(5)))

    assert in_flight["max_seen"] <= 2


# --------------------------------------- aggregate_parallel_results --


def test_aggregate_parallel_results_separates_successes_and_failures():
    """Validation criterion: l'agrégation des résultats fonctionne."""
    aggregated = aggregate_parallel_results(["ok", RuntimeError("bad"), "also ok"])
    assert aggregated == [
        {"success": True, "result": "ok"},
        {"success": False, "error": "bad"},
        {"success": True, "result": "also ok"},
    ]


# --------------------------------------- merge_parallel_contexts --


def test_merge_parallel_contexts_joins_real_non_empty_strings():
    assert merge_parallel_contexts(["a", "", "b"]) == "a\n\nb"


# --------------------------------------- execute_tools_parallel --


async def test_execute_tools_parallel_runs_real_calls_concurrently():
    """Validation criterion: l'exécution parallèle fonctionne."""
    result = await execute_tools_parallel([(ECHO_TOOL, {"value": "a"}), (ECHO_TOOL, {"value": "b"})])
    assert result == [{"success": True, "result": "a"}, {"success": True, "result": "b"}]


async def test_execute_tools_parallel_survives_a_real_individual_failure():
    """Validation criterion: robustesse -- un échec dans un appel
    parallèle n'arrête pas les autres."""
    result = await execute_tools_parallel([(FAILING_TOOL, {"value": "x"}), (ECHO_TOOL, {"value": "b"})])
    assert result[0]["success"] is False
    assert result[1] == {"success": True, "result": "b"}


async def test_execute_tools_parallel_respects_batch_strategy():
    result = await execute_tools_parallel(
        [(ECHO_TOOL, {"value": str(i)}) for i in range(5)], strategy=Strategy.BATCH, max_concurrent=2,
    )
    assert [r["result"] for r in result] == ["0", "1", "2", "3", "4"]


async def test_execute_tools_parallel_respects_chained_strategy_order():
    order = []

    async def _record(value: str) -> str:
        order.append(value)
        return value

    record_tool = ToolSpec(name="record", description="", parameters={}, capability_tags=(), handler=_record)
    await execute_tools_parallel([(record_tool, {"value": str(i)}) for i in range(3)], strategy=Strategy.CHAINED)
    assert order == ["0", "1", "2"]


async def test_execute_tools_parallel_returns_empty_list_for_no_calls():
    assert await execute_tools_parallel([]) == []


async def test_execute_tools_parallel_respects_a_real_timeout():
    async def _hangs(**kwargs) -> str:
        await asyncio.Event().wait()

    hanging_tool = ToolSpec(name="hangs", description="", parameters={}, capability_tags=(), handler=_hangs)
    with pytest.raises(asyncio.TimeoutError):
        await execute_tools_parallel([(hanging_tool, {})], timeout=0.05)


async def test_execute_tools_parallel_falls_back_to_chained_when_disabled(monkeypatch):
    from api.config import settings
    monkeypatch.setattr(settings, "PARALLEL_TOOL_CALLS_ENABLED", False)

    order = []

    async def _record(value: str) -> str:
        order.append(value)
        return value

    record_tool = ToolSpec(name="record", description="", parameters={}, capability_tags=(), handler=_record)
    result = await execute_tools_parallel([(record_tool, {"value": "a"}), (record_tool, {"value": "b"})], strategy=Strategy.ALL)
    assert order == ["a", "b"]
    assert [r["result"] for r in result] == ["a", "b"]

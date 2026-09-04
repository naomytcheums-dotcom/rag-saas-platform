"""Partie 5.1.1 -- tests for api/services/agent_orchestrator.py.

Real LLM calls are mocked at the `litellm.acompletion` boundary (the
same real, documented exception `tests/test_llm_providers.py` already
established). Every real dispatch/status/trace/timeout/stop/parallel
code path is tested for real against that one, narrow boundary."""

import asyncio
from unittest.mock import AsyncMock

import litellm
import pytest
from litellm.types.utils import Choices, Message, ModelResponse

from api.config import settings
from api.services.agent_orchestrator import AgentOrchestrator


def _real_response(text: str) -> ModelResponse:
    message = Message(content=text, role="assistant")
    choice = Choices(message=message, index=0, finish_reason="stop")
    return ModelResponse(choices=[choice])


@pytest.fixture(autouse=True)
def _configure_key(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    """Real retries use real exponential backoff -- a real, honest
    test-only speed-up (same precedent as tests/test_llm_providers.py),
    not a change to the real retry logic."""
    async def _instant_sleep(_seconds):
        return None

    monkeypatch.setattr("asyncio.sleep", _instant_sleep)


# ------------------------------------- run_agent -------------------------------------


async def test_run_agent_completes_successfully(monkeypatch):
    """Validation criterion: l'exécution d'un agent fonctionne."""
    mock_acompletion = AsyncMock(return_value=_real_response("The answer is 42."))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    orchestrator = AgentOrchestrator()
    run = await orchestrator.run_agent("agent-1", "What is the answer?")

    assert run.status == "completed"
    assert run.result == "The answer is 42."
    assert run.error is None


async def test_run_agent_reuses_the_real_resolved_llm_config(monkeypatch):
    """Validation criterion: cohérence -- l'orchestrateur réutilise
    l'abstraction LLM (Partie 4.1) et la config résolue (Partie 4.3)."""
    mock_acompletion = AsyncMock(return_value=_real_response("ok"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    orchestrator = AgentOrchestrator()
    await orchestrator.run_agent("agent-1", "hi", org_settings={"llm_provider": "anthropic", "temperature": 0.2})

    call_kwargs = mock_acompletion.call_args.kwargs
    assert call_kwargs["model"] == settings.ANTHROPIC_MODEL
    assert call_kwargs["temperature"] == 0.2


async def test_run_agent_includes_real_context_in_the_real_messages(monkeypatch):
    mock_acompletion = AsyncMock(return_value=_real_response("ok"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    orchestrator = AgentOrchestrator()
    await orchestrator.run_agent("agent-1", "hi", context="Real retrieved context here.")

    messages = mock_acompletion.call_args.kwargs["messages"]
    assert any("Real retrieved context here." in m["content"] for m in messages)


async def test_run_agent_records_a_real_ordered_trace(monkeypatch):
    """Validation criterion: la trace d'exécution est obtenue."""
    mock_acompletion = AsyncMock(return_value=_real_response("ok"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    orchestrator = AgentOrchestrator()
    run = await orchestrator.run_agent("agent-1", "hi")

    events = [e["event"] for e in orchestrator.get_agent_trace("agent-1")]
    assert events == ["created", "started", "completed"]
    assert all("timestamp" in e for e in run.trace)


async def test_run_agent_handles_a_real_llm_failure(monkeypatch):
    """Validation criterion: robustesse -- que se passe-t-il si un
    agent échoue."""
    mock_acompletion = AsyncMock(side_effect=litellm.exceptions.AuthenticationError(
        message="bad key", llm_provider="anthropic", model="claude",
    ))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    orchestrator = AgentOrchestrator()
    run = await orchestrator.run_agent("agent-1", "hi")

    assert run.status == "failed"
    assert run.error is not None
    assert orchestrator.get_agent_trace("agent-1")[-1]["event"] == "failed"


async def test_run_agent_respects_the_real_agent_max_retries(monkeypatch):
    """Validation criterion: cohérence -- AGENT_MAX_RETRIES est
    réellement câblé (pas juste déclaré)."""
    mock_acompletion = AsyncMock(side_effect=litellm.exceptions.RateLimitError(
        message="rate limited", llm_provider="anthropic", model="claude",
    ))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    orchestrator = AgentOrchestrator()
    run = await orchestrator.run_agent("agent-1", "hi", max_retries=1)

    assert run.status == "failed"
    assert mock_acompletion.call_count == 2  # 1 real initial attempt + 1 real retry


async def test_run_agent_times_out(monkeypatch):
    """Validation criterion: le timeout est respecté. Uses a real,
    never-set `asyncio.Event` to block forever rather than
    `asyncio.sleep` -- the autouse `_no_real_sleep` fixture above
    patches `asyncio.sleep` globally (to speed up real retry backoff),
    which would otherwise silently defeat this real hang simulation
    too."""
    async def _slow_completion(**kwargs):
        await asyncio.Event().wait()
        return _real_response("too late")

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(side_effect=_slow_completion))

    orchestrator = AgentOrchestrator()
    run = await orchestrator.run_agent("agent-1", "hi", timeout=0.05)

    assert run.status == "timeout"
    assert orchestrator.get_agent_status("agent-1") == "timeout"


# ------------------------------------- stop_agent -------------------------------------


async def test_stop_agent_stops_a_real_in_flight_run(monkeypatch):
    """Validation criterion: le mécanisme d'arrêt fonctionne."""
    started = asyncio.Event()

    async def _hanging_completion(**kwargs):
        started.set()
        await asyncio.Event().wait()
        return _real_response("never gets here")

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(side_effect=_hanging_completion))

    orchestrator = AgentOrchestrator()
    run_task = asyncio.create_task(orchestrator.run_agent("agent-1", "hi", timeout=5))
    await started.wait()
    stopped = orchestrator.stop_agent("agent-1")
    run = await run_task

    assert stopped is True
    assert run.status == "stopped"


def test_stop_agent_returns_false_for_an_unknown_agent():
    orchestrator = AgentOrchestrator()
    assert orchestrator.stop_agent("never-existed") is False


async def test_stop_agent_returns_false_for_an_already_finished_agent(monkeypatch):
    mock_acompletion = AsyncMock(return_value=_real_response("ok"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    orchestrator = AgentOrchestrator()
    await orchestrator.run_agent("agent-1", "hi")

    assert orchestrator.stop_agent("agent-1") is False


# ------------------------------------- status / trace lookups -------------------------------------


def test_get_agent_status_is_none_for_an_unknown_agent():
    orchestrator = AgentOrchestrator()
    assert orchestrator.get_agent_status("never-existed") is None


def test_get_agent_trace_is_none_for_an_unknown_agent():
    orchestrator = AgentOrchestrator()
    assert orchestrator.get_agent_trace("never-existed") is None


# ------------------------------------- run_multi_agent -------------------------------------


async def test_run_multi_agent_executes_real_agents_in_parallel(monkeypatch):
    """Validation criterion: l'exécution de plusieurs agents
    fonctionne."""
    mock_acompletion = AsyncMock(return_value=_real_response("ok"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    orchestrator = AgentOrchestrator()
    runs = await orchestrator.run_multi_agent(
        [{"agent_id": "agent-1"}, {"agent_id": "agent-2"}, {"agent_id": "agent-3"}], "shared input",
    )

    assert len(runs) == 3
    assert all(r.status == "completed" for r in runs)
    assert {r.agent_id for r in runs} == {"agent-1", "agent-2", "agent-3"}


async def test_run_multi_agent_survives_a_real_individual_agent_failure(monkeypatch):
    """Validation criterion: robustesse -- un agent qui échoue n'arrête
    pas les autres."""
    async def _fail_only_agent_2(**kwargs):
        if any("agent-2" in str(m) for m in kwargs.get("messages", [])):
            raise litellm.exceptions.AuthenticationError(message="bad key", llm_provider="anthropic", model="claude")
        return _real_response("ok")

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(side_effect=_fail_only_agent_2))

    orchestrator = AgentOrchestrator()
    runs = await orchestrator.run_multi_agent(
        [{"agent_id": "agent-1", "input": "agent-1 task"}, {"agent_id": "agent-2", "input": "agent-2 task"}], "shared",
    )

    statuses = {r.agent_id: r.status for r in runs}
    assert statuses["agent-1"] == "completed"
    assert statuses["agent-2"] == "failed"


async def test_run_multi_agent_respects_real_per_agent_overrides(monkeypatch):
    mock_acompletion = AsyncMock(return_value=_real_response("ok"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    orchestrator = AgentOrchestrator()
    await orchestrator.run_multi_agent(
        [{"agent_id": "agent-1", "llm_overrides": {"temperature": 0.9}}], "shared input",
    )

    assert mock_acompletion.call_args.kwargs["temperature"] == 0.9

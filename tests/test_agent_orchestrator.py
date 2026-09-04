"""Partie 5.1.1 -- tests for api/services/agent_orchestrator.py and its
persistence fix (api/models/agent_run.py, api/security/agent_runs.py).

Real LLM calls are mocked at the `litellm.acompletion` boundary (the
same real, documented exception `tests/test_llm_providers.py` already
established). Every real dispatch/status/trace/timeout/stop/parallel/
persistence code path is tested for real against that one, narrow
boundary -- the real SQLite `db_session` fixture backs every DB
operation for real, no DB mocking."""

import asyncio
import uuid
from unittest.mock import AsyncMock

import litellm
import pytest
from litellm.types.utils import Choices, Message, ModelResponse

from api.config import settings
from api.models.agent_run import AgentRunRecord
from api.security.agent_runs import get_run, get_runs
from api.services.agent_orchestrator import AgentOrchestrator
from api.security.tool_permissions import grant_tool_permission
from api.services.tools import CALCULATOR_TOOL, WORD_COUNT_TOOL


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


async def test_run_agent_completes_successfully(monkeypatch, db_session):
    """Validation criterion: l'exécution d'un agent fonctionne."""
    mock_acompletion = AsyncMock(return_value=_real_response("The answer is 42."))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    orchestrator = AgentOrchestrator()
    run = await orchestrator.run_agent("agent-1", "What is the answer?", db=db_session)

    assert run.status == "completed"
    assert run.result == "The answer is 42."
    assert run.error is None


async def test_run_agent_reuses_the_real_resolved_llm_config(monkeypatch, db_session):
    """Validation criterion: cohérence -- l'orchestrateur réutilise
    l'abstraction LLM (Partie 4.1) et la config résolue (Partie 4.3)."""
    mock_acompletion = AsyncMock(return_value=_real_response("ok"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    orchestrator = AgentOrchestrator()
    await orchestrator.run_agent("agent-1", "hi", db=db_session, org_settings={"llm_provider": "anthropic", "temperature": 0.2})

    call_kwargs = mock_acompletion.call_args.kwargs
    assert call_kwargs["model"] == settings.ANTHROPIC_MODEL
    assert call_kwargs["temperature"] == 0.2


async def test_run_agent_includes_real_context_in_the_real_messages(monkeypatch, db_session):
    mock_acompletion = AsyncMock(return_value=_real_response("ok"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    orchestrator = AgentOrchestrator()
    await orchestrator.run_agent("agent-1", "hi", db=db_session, context="Real retrieved context here.")

    messages = mock_acompletion.call_args.kwargs["messages"]
    assert any("Real retrieved context here." in m["content"] for m in messages)


async def test_run_agent_records_a_real_ordered_trace(monkeypatch, db_session):
    """Validation criterion: la trace d'exécution est obtenue."""
    mock_acompletion = AsyncMock(return_value=_real_response("ok"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    orchestrator = AgentOrchestrator()
    run = await orchestrator.run_agent("agent-1", "hi", db=db_session)

    trace = await orchestrator.get_agent_trace("agent-1", db_session)
    events = [e["event"] for e in trace]
    assert events == ["created", "started", "completed"]
    assert all("timestamp" in e for e in run.trace)


async def test_run_agent_handles_a_real_llm_failure(monkeypatch, db_session):
    """Validation criterion: robustesse -- que se passe-t-il si un
    agent échoue."""
    mock_acompletion = AsyncMock(side_effect=litellm.exceptions.AuthenticationError(
        message="bad key", llm_provider="anthropic", model="claude",
    ))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    orchestrator = AgentOrchestrator()
    run = await orchestrator.run_agent("agent-1", "hi", db=db_session)

    assert run.status == "failed"
    assert run.error is not None
    trace = await orchestrator.get_agent_trace("agent-1", db_session)
    assert trace[-1]["event"] == "failed"


async def test_run_agent_respects_the_real_agent_max_retries(monkeypatch, db_session):
    """Validation criterion: cohérence -- AGENT_MAX_RETRIES est
    réellement câblé (pas juste déclaré)."""
    mock_acompletion = AsyncMock(side_effect=litellm.exceptions.RateLimitError(
        message="rate limited", llm_provider="anthropic", model="claude",
    ))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    orchestrator = AgentOrchestrator()
    run = await orchestrator.run_agent("agent-1", "hi", db=db_session, max_retries=1)

    assert run.status == "failed"
    assert mock_acompletion.call_count == 2  # 1 real initial attempt + 1 real retry


async def test_run_agent_times_out(monkeypatch, db_session):
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
    run = await orchestrator.run_agent("agent-1", "hi", db=db_session, timeout=0.05)

    assert run.status == "timeout"
    assert await orchestrator.get_agent_status("agent-1", db_session) == "timeout"


# ------------------------------------- tools (Partie 5.1.2 integration) -------------------------------------


async def test_run_agent_selects_and_traces_real_tools(monkeypatch, db_session):
    """Validation criterion: cohérence -- la sélection d'outils est
    intégrée dans l'orchestrateur (Partie 5.1.2)."""
    mock_acompletion = AsyncMock(return_value=_real_response("ok"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    orchestrator = AgentOrchestrator()
    run = await orchestrator.run_agent(
        "agent-1", "calculator math", db=db_session,
        tools=[CALCULATOR_TOOL, WORD_COUNT_TOOL],
    )

    trace_event = next(e for e in run.trace if e["event"] == "tools_selected")
    assert "calculator" in trace_event["tools"]
    system_message = mock_acompletion.call_args.kwargs["messages"][0]["content"]
    assert "calculator" in system_message


async def test_run_agent_with_no_relevant_tools_still_completes(monkeypatch, db_session):
    """Validation criterion: robustesse -- que se passe-t-il si aucun
    outil n'est sélectionné."""
    mock_acompletion = AsyncMock(return_value=_real_response("ok"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    orchestrator = AgentOrchestrator()
    run = await orchestrator.run_agent(
        "agent-1", "completely unrelated xyz topic", db=db_session,
        tools=[CALCULATOR_TOOL],
    )

    assert run.status == "completed"
    trace_event = next(e for e in run.trace if e["event"] == "tools_selected")
    assert trace_event["tools"] == []


# ------------------------------------- memory (Partie 5.1.11 integration) -------------------------------------


async def test_run_agent_loads_real_memory_into_the_system_prompt(monkeypatch, db_session):
    """Validation criterion: cohérence -- la mémoire est partagée entre
    les appels (chargée dans le prompt de l'appel suivant)."""
    from api.services.agent_memory import add_to_memory, create_session

    mock_acompletion = AsyncMock(return_value=_real_response("ok"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    session = await create_session(db_session, "agent-1")
    await add_to_memory(db_session, session.id, "favorite_color", "blue")
    await db_session.commit()

    orchestrator = AgentOrchestrator()
    run = await orchestrator.run_agent("agent-1", "what do I like?", db=db_session, session_id=session.id)

    assert run.status == "completed"
    system_message = mock_acompletion.call_args.kwargs["messages"][0]["content"]
    assert "blue" in system_message
    assert any(e["event"] == "memory_loaded" for e in run.trace)


# ------------------------------------- conversation (Partie 5.1.12 integration) -------------------------------------


async def test_run_agent_loads_and_extends_a_real_conversation(monkeypatch, db_session):
    """Validation criterion: cohérence -- l'historique est chargé et la
    continuité fonctionne entre appels successifs."""
    from api.security.conversations import create_conversation, get_conversation_messages

    mock_acompletion = AsyncMock(return_value=_real_response("Nice to meet you too!"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    conversation = await create_conversation(db_session, "agent-1", uuid.uuid4(), "Test")
    await db_session.commit()

    orchestrator = AgentOrchestrator()
    run = await orchestrator.run_agent("agent-1", "Nice to meet you!", db=db_session, conversation_id=conversation.id)

    assert run.status == "completed"
    messages = await get_conversation_messages(db_session, conversation.id)
    assert [m.role for m in messages] == ["user", "assistant"]
    assert messages[0].content == "Nice to meet you!"
    assert messages[1].content == "Nice to meet you too!"


async def test_run_agent_replays_real_prior_conversation_turns(monkeypatch, db_session):
    from api.security.conversations import add_message, create_conversation

    mock_acompletion = AsyncMock(return_value=_real_response("ok"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    conversation = await create_conversation(db_session, "agent-1", uuid.uuid4(), "Test")
    await add_message(db_session, conversation.id, "user", "my name is Ada")
    await add_message(db_session, conversation.id, "assistant", "hi Ada")
    await db_session.commit()

    orchestrator = AgentOrchestrator()
    await orchestrator.run_agent("agent-1", "what's my name?", db=db_session, conversation_id=conversation.id)

    messages = mock_acompletion.call_args.kwargs["messages"]
    contents = [m["content"] for m in messages]
    assert "my name is Ada" in contents
    assert "hi Ada" in contents


async def test_run_agent_excludes_a_real_denied_tool(monkeypatch, db_session):
    """Validation criterion: sécurité (Partie 5.1.3) -- si l'utilisateur
    n'a pas la permission, l'outil est désactivé (jamais sélectionné,
    jamais décrit au LLM)."""
    mock_acompletion = AsyncMock(return_value=_real_response("ok"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    await grant_tool_permission(db_session, org_id, None, user_id, "calculator", "deny", granted_by=None)
    await db_session.commit()

    orchestrator = AgentOrchestrator()
    run = await orchestrator.run_agent(
        "agent-1", "calculator math", db=db_session, tools=[CALCULATOR_TOOL, WORD_COUNT_TOOL],
        organization_id=org_id, created_by=user_id,
    )

    trace_event = next(e for e in run.trace if e["event"] == "tools_selected")
    assert "calculator" not in trace_event["tools"]
    system_message = mock_acompletion.call_args.kwargs["messages"][0]["content"]
    assert "calculator" not in system_message


# ------------------------------------- persistence (fix) -------------------------------------


async def test_run_agent_persists_the_real_run_row(monkeypatch, db_session):
    """Validation criterion: la création d'un run fonctionne, et les
    runs sont persistants (real agent_runs table row, not just an
    in-memory object)."""
    mock_acompletion = AsyncMock(return_value=_real_response("ok"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    orchestrator = AgentOrchestrator()
    run = await orchestrator.run_agent("agent-1", "hi", db=db_session)

    row = await get_run(db_session, run.id)
    assert row is not None
    assert row.status == "completed"
    assert row.result == "ok"
    assert row.input == "hi"


async def test_get_agent_status_reads_from_a_real_second_orchestrator_instance(monkeypatch, db_session):
    """Validation criterion: le statut est mis à jour, et est lisible
    depuis un AUTRE `AgentOrchestrator` (simulates a different worker
    process reading the same real DB row -- the whole point of the
    fix)."""
    mock_acompletion = AsyncMock(return_value=_real_response("ok"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    writer = AgentOrchestrator()
    await writer.run_agent("agent-1", "hi", db=db_session)

    reader = AgentOrchestrator()  # a genuinely separate instance, own empty self._tasks
    assert await reader.get_agent_status("agent-1", db_session) == "completed"


async def test_get_runs_scopes_by_the_real_organization_id(monkeypatch, db_session):
    """Validation criterion: les permissions sont respectées -- un run
    créé for organization A is invisible to a lookup scoped to
    organization B, even for the same agent_id."""
    mock_acompletion = AsyncMock(return_value=_real_response("ok"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    orchestrator = AgentOrchestrator()
    await orchestrator.run_agent("shared-agent-id", "hi", db=db_session, organization_id=org_a)

    assert await orchestrator.get_agent_status("shared-agent-id", db_session, organization_id=org_a) == "completed"
    assert await orchestrator.get_agent_status("shared-agent-id", db_session, organization_id=org_b) is None

    org_a_runs = await get_runs(db_session, "shared-agent-id", organization_id=org_a)
    org_b_runs = await get_runs(db_session, "shared-agent-id", organization_id=org_b)
    assert len(org_a_runs) == 1
    assert len(org_b_runs) == 0


async def test_run_agent_records_the_real_created_by_user(monkeypatch, db_session):
    mock_acompletion = AsyncMock(return_value=_real_response("ok"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    user_id = uuid.uuid4()
    orchestrator = AgentOrchestrator()
    run = await orchestrator.run_agent("agent-1", "hi", db=db_session, created_by=user_id)

    assert run.created_by == user_id


# ------------------------------------- stop_agent -------------------------------------


async def test_stop_agent_stops_a_real_in_flight_run(monkeypatch, db_session):
    """Validation criterion: le mécanisme d'arrêt fonctionne."""
    started = asyncio.Event()

    async def _hanging_completion(**kwargs):
        started.set()
        await asyncio.Event().wait()
        return _real_response("never gets here")

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(side_effect=_hanging_completion))

    orchestrator = AgentOrchestrator()
    run_task = asyncio.create_task(orchestrator.run_agent("agent-1", "hi", db=db_session, timeout=5))
    await started.wait()
    stopped = await orchestrator.stop_agent("agent-1", db_session)
    run = await run_task

    assert stopped is True
    assert run.status == "stopped"


async def test_stop_agent_returns_false_for_an_unknown_agent(db_session):
    orchestrator = AgentOrchestrator()
    assert await orchestrator.stop_agent("never-existed", db_session) is False


async def test_stop_agent_returns_false_for_an_already_finished_agent(monkeypatch, db_session):
    mock_acompletion = AsyncMock(return_value=_real_response("ok"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    orchestrator = AgentOrchestrator()
    await orchestrator.run_agent("agent-1", "hi", db=db_session)

    assert await orchestrator.stop_agent("agent-1", db_session) is False


# ------------------------------------- status / trace lookups -------------------------------------


async def test_get_agent_status_is_none_for_an_unknown_agent(db_session):
    orchestrator = AgentOrchestrator()
    assert await orchestrator.get_agent_status("never-existed", db_session) is None


async def test_get_agent_trace_is_none_for_an_unknown_agent(db_session):
    orchestrator = AgentOrchestrator()
    assert await orchestrator.get_agent_trace("never-existed", db_session) is None


# ------------------------------------- run_multi_agent -------------------------------------


async def test_run_multi_agent_executes_real_agents_in_parallel(monkeypatch, db_session):
    """Validation criterion: l'exécution de plusieurs agents
    fonctionne -- real, concurrent chat_completion calls sharing one
    real db session safely (see agent_orchestrator.py's own
    self._db_lock)."""
    mock_acompletion = AsyncMock(return_value=_real_response("ok"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    orchestrator = AgentOrchestrator()
    runs = await orchestrator.run_multi_agent(
        [{"agent_id": "agent-1"}, {"agent_id": "agent-2"}, {"agent_id": "agent-3"}], "shared input", db=db_session,
    )

    assert len(runs) == 3
    assert all(r.status == "completed" for r in runs)
    assert {r.agent_id for r in runs} == {"agent-1", "agent-2", "agent-3"}
    assert isinstance(runs[0], AgentRunRecord)


async def test_run_multi_agent_survives_a_real_individual_agent_failure(monkeypatch, db_session):
    """Validation criterion: robustesse -- un agent qui échoue n'arrête
    pas les autres."""
    async def _fail_only_agent_2(**kwargs):
        if any("agent-2" in str(m) for m in kwargs.get("messages", [])):
            raise litellm.exceptions.AuthenticationError(message="bad key", llm_provider="anthropic", model="claude")
        return _real_response("ok")

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(side_effect=_fail_only_agent_2))

    orchestrator = AgentOrchestrator()
    runs = await orchestrator.run_multi_agent(
        [{"agent_id": "agent-1", "input": "agent-1 task"}, {"agent_id": "agent-2", "input": "agent-2 task"}], "shared", db=db_session,
    )

    statuses = {r.agent_id: r.status for r in runs}
    assert statuses["agent-1"] == "completed"
    assert statuses["agent-2"] == "failed"


async def test_run_multi_agent_respects_real_per_agent_overrides(monkeypatch, db_session):
    mock_acompletion = AsyncMock(return_value=_real_response("ok"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    orchestrator = AgentOrchestrator()
    await orchestrator.run_multi_agent(
        [{"agent_id": "agent-1", "llm_overrides": {"temperature": 0.9}}], "shared input", db=db_session,
    )

    assert mock_acompletion.call_args.kwargs["temperature"] == 0.9

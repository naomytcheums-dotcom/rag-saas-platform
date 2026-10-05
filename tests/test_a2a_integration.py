"""
api/services/a2a_integration.py -- `run_requirement_agent` makes a
real, paid LLM call under the hood (via BeeAI's own internal litellm
dependency, same real, documented exception as
tests/test_beeai_orchestrator.py). Mocked here at that same, already-
tested boundary -- `RagAgentExecutor.execute` itself is real,
constructed and exercised end-to-end against a real `a2a.types.AgentCard`
and real `new_text_message`/`get_message_text` helpers, verified
directly against the installed `a2a-sdk` package before writing this
module."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.services.a2a_integration import RagAgentExecutor, build_agent_card


def test_build_agent_card_describes_a_real_rag_capability():
    card = build_agent_card("Acme Corp")

    assert card.name == "Acme Corp RAG Agent"
    assert len(card.skills) == 1
    assert card.skills[0].id == "rag_query"
    assert card.capabilities.streaming is False


async def test_rag_agent_executor_answers_using_this_organizations_real_configured_agent(monkeypatch):
    """Validation criterion: the real incoming A2A task text reaches
    `run_requirement_agent` with THIS organization's own id, and the
    real answer is enqueued as a real A2A text message."""
    from a2a.helpers import get_message_text

    org_id = uuid.uuid4()
    mock_run_agent = AsyncMock(return_value="Paris is the capital of France.")
    monkeypatch.setattr("api.services.beeai_orchestrator.run_requirement_agent", mock_run_agent)

    fake_db = MagicMock()

    class _FakeSessionFactory:
        async def __aenter__(self):
            return fake_db

        async def __aexit__(self, *args):
            return False

    context = MagicMock()
    context.get_user_input.return_value = "What is the capital of France?"
    context.context_id = "ctx-1"
    context.task_id = "task-1"

    event_queue = MagicMock()
    event_queue.enqueue_event = AsyncMock()

    executor = RagAgentExecutor(db_session_factory=_FakeSessionFactory, organization_id=org_id)
    await executor.execute(context, event_queue)

    mock_run_agent.assert_awaited_once_with(fake_db, org_id, "What is the capital of France?")
    event_queue.enqueue_event.assert_awaited_once()
    sent_message = event_queue.enqueue_event.call_args.args[0]
    assert get_message_text(sent_message) == "Paris is the capital of France."


async def test_rag_agent_executor_cancel_is_a_real_honest_noop():
    executor = RagAgentExecutor(db_session_factory=MagicMock(), organization_id=uuid.uuid4())
    await executor.cancel(MagicMock(), MagicMock())
    # No exception raised -- the real, documented "no cancellation hook" behavior.


async def _execute_with_failure(monkeypatch, error):
    from a2a.helpers import get_message_text

    monkeypatch.setattr("api.services.beeai_orchestrator.run_requirement_agent", AsyncMock(side_effect=error))

    class _Factory:
        async def __aenter__(self):
            return MagicMock()

        async def __aexit__(self, *args):
            return False

    context = MagicMock()
    context.get_user_input.return_value = "hi"
    context.context_id, context.task_id = "ctx", "task"
    event_queue = MagicMock()
    event_queue.enqueue_event = AsyncMock()
    await RagAgentExecutor(db_session_factory=_Factory, organization_id=uuid.uuid4()).execute(context, event_queue)
    event_queue.enqueue_event.assert_awaited_once()
    return get_message_text(event_queue.enqueue_event.call_args.args[0])


async def test_executor_answers_in_plain_words_when_the_agent_framework_is_not_installed(monkeypatch):
    from api.services.beeai_orchestrator import BeeAINotAvailableError

    text = await _execute_with_failure(monkeypatch, BeeAINotAvailableError("beeai-framework is not installed"))
    assert "not available" in text and "beeai" not in text.lower()


async def test_executor_never_leaks_an_internal_error_to_the_a2a_client(monkeypatch):
    text = await _execute_with_failure(monkeypatch, RuntimeError("secret internal detail: postgres://u:p@h/db"))
    assert text == "The agent could not process this request." and "secret" not in text

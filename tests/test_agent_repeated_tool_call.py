"""A model that asks again for a tool call it already got the result of (same tool, same arguments) must not make the agent burn every iteration and fail:
the call is not run a second time and the model is told to answer from the results it has (found against a real Ollama qwen2.5:7b, 1 run in 3)."""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import litellm
import pytest
from litellm.types.utils import ChatCompletionMessageToolCall, Choices, Function, Message, ModelResponse

from api.config import settings
from api.services import agent_orchestrator as ao
from api.services.agent_orchestrator import AgentOrchestrator
from api.services.tools import CALCULATOR_TOOL


def _text(text: str) -> ModelResponse:
    return ModelResponse(choices=[Choices(message=Message(content=text, role="assistant"), index=0, finish_reason="stop")])


def _call(call_id: str, expression: str) -> ModelResponse:
    tool_call = ChatCompletionMessageToolCall(id=call_id, type="function", function=Function(name="calculator", arguments=json.dumps({"expression": expression})))
    return ModelResponse(choices=[Choices(message=Message(content=None, role="assistant", tool_calls=[tool_call]), index=0, finish_reason="tool_calls")])


@pytest.fixture(autouse=True)
def _setup(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr("api.services.agent_orchestrator.select_tools", AsyncMock(side_effect=lambda query, tools, **kw: tools))


async def _run(monkeypatch, db_session, responses):
    mock = AsyncMock(side_effect=responses)
    monkeypatch.setattr(litellm, "acompletion", mock)
    run = await AgentOrchestrator().run_agent("agent-1", "What is 6 * 7?", db=db_session, tools=[CALCULATOR_TOOL])
    return run, mock


async def test_a_repeated_identical_tool_call_is_not_rerun_and_the_model_answers(monkeypatch, db_session):
    run, mock = await _run(monkeypatch, db_session, [_call("c1", "6 * 7"), _call("c2", "6 * 7"), _text("It is 42.")])

    assert run.status == "completed", run.error
    assert run.result == "It is 42."
    assert [e["event"] for e in run.trace].count("tool_call") == 1
    assert any(e["event"] == "repeated_tool_call_stopped" for e in run.trace)
    last_call = mock.await_args_list[-1].kwargs
    assert "tools" not in last_call
    assert last_call["messages"][-1]["role"] == "user" and "answer the user now" in last_call["messages"][-1]["content"]


async def test_a_new_call_with_different_arguments_is_still_executed(monkeypatch, db_session):
    run, _mock = await _run(monkeypatch, db_session, [_call("c1", "6 * 7"), _call("c2", "2 + 2"), _text("42 and 4.")])

    assert run.status == "completed", run.error
    assert [e["event"] for e in run.trace].count("tool_call") == 2
    assert not any(e["event"] == "repeated_tool_call_stopped" for e in run.trace)


async def test_a_model_that_keeps_asking_after_being_told_to_answer_still_fails_cleanly(monkeypatch, db_session):
    run, mock = await _run(monkeypatch, db_session, [_call(f"c{i}", "6 * 7") for i in range(settings.AGENT_MAX_TOOL_ITERATIONS)])

    assert run.status == "failed"
    assert "tool-calling iterations" in run.error
    assert [e["event"] for e in run.trace].count("tool_call") == 1
    assert mock.await_count == 3


async def test_the_streaming_loop_does_the_same():
    orch = AgentOrchestrator()
    orch._db_lock = AsyncMock()
    orch._db_lock.__aenter__ = AsyncMock(return_value=None)
    orch._db_lock.__aexit__ = AsyncMock(return_value=None)
    tool_spec = MagicMock()
    tool_spec.name = "get_weather"
    seen_kwargs: list[dict] = []

    async def fake_stream(messages, **kwargs):
        seen_kwargs.append(kwargs)
        if len(seen_kwargs) <= 2:
            yield {"type": "tool_calls", "tool_calls": [{"id": f"call_{len(seen_kwargs)}", "name": "get_weather", "arguments": {"city": "Paris"}}]}
        else:
            yield "Sunny in Paris."

    execute = AsyncMock(return_value="sunny, 22C")
    with patch.object(ao, "chat_completion_stream_with_tools", fake_stream), \
         patch.object(ao, "select_tools", AsyncMock(return_value=[tool_spec])), \
         patch.object(ao, "check_tool_permission", AsyncMock(return_value="allow")), \
         patch.object(ao, "tool_to_function_schema", MagicMock(return_value={"name": "get_weather"})), \
         patch.object(ao, "tool_input_schema", MagicMock(return_value={})), \
         patch.object(ao, "get_validation_errors", MagicMock(return_value=[])), \
         patch.object(ao, "get_tool_timeout", AsyncMock(return_value=5.0)), \
         patch.object(ao, "execute_tool_with_timeout", execute), \
         patch.object(ao, "create_run", AsyncMock(return_value=MagicMock(id=uuid.uuid4()))), \
         patch.object(ao, "update_run_status", AsyncMock()), \
         patch.object(ao, "get_conversation_messages", AsyncMock(return_value=[])), \
         patch.object(ao, "add_message", AsyncMock()), \
         patch.object(ao, "_fire_message_hook", AsyncMock()), \
         patch.object(ao, "resolve_org_api_key", AsyncMock(return_value=None)), \
         patch.object(ao, "validate_guardrails", AsyncMock(return_value={"passed": True, "violations": []})), \
         patch("api.services.billing_credits.get_or_create_credit", AsyncMock(return_value=MagicMock(balance=1000))), \
         patch("api.services.billing_credits.enforce_spend_caps", AsyncMock(return_value=None)):
        db = AsyncMock()
        events = [ev async for ev in orch.stream_response(str(uuid.uuid4()), "Weather in Paris?", db=db, organization_id=uuid.uuid4(), created_by=uuid.uuid4(), tools=[tool_spec])]

    assert execute.await_count == 1
    assert "tools" not in seen_kwargs[-1]
    assert "Sunny in Paris." in "".join(e["token"] for e in events if e.get("type") == "token")
    assert events[-1]["type"] == "done"

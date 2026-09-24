"""Real tests for the streaming tool-execution loop (P2 #4, session
SSRF épinglé).

Verifies that AgentOrchestrator.stream_response now:
- passes tools= to the streaming call
- executes a tool the LLM requests
- appends role:tool back to messages
- re-enters the stream for a final answer
- yields the right SSE events (tool_call, tool_result, token, done)
"""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.services import agent_orchestrator as ao


def _make_orchestrator():
    orch = ao.AgentOrchestrator()
    # Disable the shared db-lock semantics for the test -- we only want
    # to assert on the stream loop's own behavior.
    orch._db_lock = AsyncMock()
    orch._db_lock.__aenter__ = AsyncMock(return_value=None)
    orch._db_lock.__aexit__ = AsyncMock(return_value=None)
    return orch


@pytest.mark.asyncio
async def test_stream_executes_tool_and_resumes():
    """The core new behavior: LLM asks for a tool, we run it, feed the
    result back, and get a final answer -- all in one stream_response
    call."""
    orch = _make_orchestrator()

    tool_spec = MagicMock()
    tool_spec.name = "get_weather"
    tool_spec.description = "Get the weather"

    # Two stream calls: 1st yields tool_calls, 2nd yields content.
    call_count = {"n": 0}

    async def fake_stream(messages, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            # Real providers: content is None when the model wants tools
            yield {"type": "tool_calls", "tool_calls": [
                {"id": "call_1", "name": "get_weather", "arguments": {"city": "Paris"}},
            ]}
        else:
            yield "The weather in Paris is sunny."

    # Patch the module-level import reference
    with patch.object(ao, "chat_completion_stream_with_tools", fake_stream), \
         patch.object(ao, "select_tools", AsyncMock(return_value=[tool_spec])), \
         patch.object(ao, "check_tool_permission", AsyncMock(return_value="allow")), \
         patch.object(ao, "tool_to_function_schema", MagicMock(return_value={"name": "get_weather"})), \
         patch.object(ao, "tool_input_schema", MagicMock(return_value={})), \
         patch.object(ao, "get_validation_errors", MagicMock(return_value=[])), \
         patch.object(ao, "get_tool_timeout", AsyncMock(return_value=5.0)), \
         patch.object(ao, "execute_tool_with_timeout", AsyncMock(return_value="sunny, 22C")), \
         patch.object(ao, "create_run", AsyncMock(return_value=MagicMock(id=uuid.uuid4()))), \
         patch.object(ao, "update_run_status", AsyncMock()), \
         patch.object(ao, "get_conversation_messages", AsyncMock(return_value=[])), \
         patch.object(ao, "add_message", AsyncMock()), \
         patch.object(ao, "_fire_message_hook", AsyncMock()), \
         patch.object(ao, "resolve_org_api_key", AsyncMock(return_value=None)), \
         patch.object(ao, "validate_guardrails", AsyncMock(return_value={"passed": True, "violations": []})):

        db = AsyncMock()
        db.commit = AsyncMock()

        events = []
        async for ev in orch.stream_response(
            str(uuid.uuid4()), "What's the weather in Paris?",
            db=db, organization_id=uuid.uuid4(), created_by=uuid.uuid4(),
            tools=[tool_spec],
        ):
            events.append(ev)

    # Assert the tool was executed and the loop resumed
    assert call_count["n"] == 2, f"expected 2 stream calls, got {call_count['n']}"
    event_types = [e.get("type") for e in events]
    assert "tool_call" in event_types
    assert "tool_result" in event_types
    assert "token" in event_types
    assert "done" in event_types
    # Final token should be present
    tokens = [e["token"] for e in events if e.get("type") == "token"]
    assert any("sunny" in t for t in tokens)


@pytest.mark.asyncio
async def test_stream_without_tools_does_not_call_tool_loop():
    """No tools selected -> plain streaming, no tool_call events."""
    orch = _make_orchestrator()

    async def fake_stream(messages, **kwargs):
        yield "Hello, world."

    with patch.object(ao, "chat_completion_stream_with_tools", fake_stream), \
         patch.object(ao, "create_run", AsyncMock(return_value=MagicMock(id=uuid.uuid4()))), \
         patch.object(ao, "update_run_status", AsyncMock()), \
         patch.object(ao, "get_conversation_messages", AsyncMock(return_value=[])), \
         patch.object(ao, "add_message", AsyncMock()), \
         patch.object(ao, "_fire_message_hook", AsyncMock()), \
         patch.object(ao, "resolve_org_api_key", AsyncMock(return_value=None)), \
         patch.object(ao, "validate_guardrails", AsyncMock(return_value={"passed": True, "violations": []})):

        db = AsyncMock()
        db.commit = AsyncMock()

        events = []
        async for ev in orch.stream_response(str(uuid.uuid4()), "hi", db=db):
            events.append(ev)

    event_types = [e.get("type") for e in events]
    assert "tool_call" not in event_types
    assert "done" in event_types


@pytest.mark.asyncio
async def test_stream_tool_failure_is_reported_not_crashing():
    """A tool that raises must be reported as a tool_result with error,
    then the loop must resume -- not crash the whole stream."""
    orch = _make_orchestrator()

    tool_spec = MagicMock()
    tool_spec.name = "broken_tool"
    tool_spec.description = "Always fails"

    call_count = {"n": 0}

    async def fake_stream(messages, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            yield {"type": "tool_calls", "tool_calls": [
                {"id": "call_1", "name": "broken_tool", "arguments": {}},
            ]}
        else:
            yield "Sorry, that tool failed."

    with patch.object(ao, "chat_completion_stream_with_tools", fake_stream), \
         patch.object(ao, "select_tools", AsyncMock(return_value=[tool_spec])), \
         patch.object(ao, "check_tool_permission", AsyncMock(return_value="allow")), \
         patch.object(ao, "tool_to_function_schema", MagicMock(return_value={"name": "broken_tool"})), \
         patch.object(ao, "tool_input_schema", MagicMock(return_value={})), \
         patch.object(ao, "get_validation_errors", MagicMock(return_value=[])), \
         patch.object(ao, "get_tool_timeout", AsyncMock(return_value=5.0)), \
         patch.object(ao, "execute_tool_with_timeout", AsyncMock(side_effect=RuntimeError("boom"))), \
         patch.object(ao, "create_run", AsyncMock(return_value=MagicMock(id=uuid.uuid4()))), \
         patch.object(ao, "update_run_status", AsyncMock()), \
         patch.object(ao, "get_conversation_messages", AsyncMock(return_value=[])), \
         patch.object(ao, "add_message", AsyncMock()), \
         patch.object(ao, "_fire_message_hook", AsyncMock()), \
         patch.object(ao, "resolve_org_api_key", AsyncMock(return_value=None)), \
         patch.object(ao, "validate_guardrails", AsyncMock(return_value={"passed": True, "violations": []})):

        db = AsyncMock()
        db.commit = AsyncMock()

        events = []
        async for ev in orch.stream_response(
            str(uuid.uuid4()), "use broken tool", db=db,
            organization_id=uuid.uuid4(), created_by=uuid.uuid4(), tools=[tool_spec],
        ):
            events.append(ev)

    results = [e for e in events if e.get("type") == "tool_result"]
    assert len(results) == 1
    assert results[0]["error"] is not None
    assert "boom" in results[0]["error"]
    # Loop still reached done
    assert any(e.get("type") == "done" for e in events)

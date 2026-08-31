"""
Unit tests for src/agent.py.

Two things are deliberately kept out of scope here, same as generation.py's
gap noted in AUDIT.md: no test calls the real Anthropic API (no credit,
and it'd be slow/flaky/non-free even with some) or the real Retriever
(loads an embedding model). Everything that touches either is exercised
through a fake/injected stand-in instead -- the GitHub tool doesn't need
an API key at all, so it's tested against a fake HTTP transport rather
than skipped.
"""

import datetime as dt
import sys
from pathlib import Path

import anthropic
import httpx
import pytest
from agentfixture import (
    FakeAnthropicClient,
    FakeResponse,
    FakeTextBlock,
    FakeToolUseBlock,
    RecordingSleep,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import agent as agent_module  # noqa: E402
from agent import Agent, _next_escalation_slot, _slim_issue, _validate_tool_input, search_github_issues  # noqa: E402


def make_api_status_error(status_code, message="error"):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status_code, request=request, json={"error": {"message": message}})
    return anthropic.APIStatusError(message, response=response, body={"error": {"message": message}})


def make_connection_error(message="Connection error."):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return anthropic.APIConnectionError(message=message, request=request)


class FixedDatetime(dt.datetime):
    """Subclassing dt.datetime (rather than a plain stand-in) so arithmetic
    on the value _next_escalation_slot() computes -- .replace(), + timedelta
    -- keeps behaving like a real datetime instead of needing its own reimplementation."""
    fixed_now = dt.datetime(2026, 8, 20, 14, 47, tzinfo=dt.timezone.utc)

    @classmethod
    def now(cls, tz=None):
        return cls.fixed_now.astimezone(tz) if tz else cls.fixed_now


class FakeCalendarClient:
    def __init__(self):
        self.calls = []

    def book_escalation(self, reason, start_time):
        self.calls.append({"reason": reason, "start_time": start_time})
        return {"event_id": "evt_1", "link": "https://calendar.example/evt_1", "start": start_time.isoformat()}


class FakeSheetsClient:
    def __init__(self):
        self.calls = []

    def log_question(self, question, category, answered):
        self.calls.append({"question": question, "category": category, "answered": answered})
        return {"logged": True}


# ---- fakes for the Anthropic client's response shape ----------------------
# FakeTextBlock, FakeToolUseBlock, FakeResponse, RecordingSleep, and
# FakeAnthropicClient now come from agentfixture (imported above) --
# extracted from this exact file once a second project needed the same
# fakes. See https://github.com/naomytcheums-dotcom/agentfixture.

# ---- fakes for httpx, used by search_github_issues -------------------------

class FakeHTTPResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://api.github.com/search/issues")
            raise httpx.HTTPStatusError("error", request=request, response=httpx.Response(self.status_code, request=request))

    def json(self):
        return self._payload


class FakeHTTPClient:
    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self._exc is not None:
            raise self._exc
        return self._response


# ---- _slim_issue -------------------------------------------------------

def test_slim_issue_keeps_only_useful_fields():
    raw = {
        "number": 42,
        "title": "Query params lost on redirect",
        "state": "open",
        "body": "long body text nobody needs echoed back...",
        "labels": [{"name": "bug"}, {"name": "needs-triage"}],
        "html_url": "https://github.com/fastapi/fastapi/issues/42",
        "comments": 3,
    }
    slim = _slim_issue(raw)
    assert slim == {
        "number": 42,
        "title": "Query params lost on redirect",
        "state": "open",
        "labels": ["bug", "needs-triage"],
        "url": "https://github.com/fastapi/fastapi/issues/42",
    }


# ---- search_github_issues -----------------------------------------------

def test_search_github_issues_filters_out_pull_requests():
    payload = {
        "items": [
            {"number": 1, "title": "A real issue", "state": "open", "labels": [], "html_url": "u1"},
            {"number": 2, "title": "A PR, not an issue", "state": "open", "labels": [], "html_url": "u2", "pull_request": {}},
        ]
    }
    fake_client = FakeHTTPClient(response=FakeHTTPResponse(payload))
    results = search_github_issues("redirect", http_client=fake_client)
    assert [r["number"] for r in results] == [1]


def test_search_github_issues_scopes_query_to_the_fastapi_repo():
    fake_client = FakeHTTPClient(response=FakeHTTPResponse({"items": []}))
    search_github_issues("websocket ping", http_client=fake_client)
    url, kwargs = fake_client.calls[0]
    assert kwargs["params"]["q"] == "repo:fastapi/fastapi is:issue in:title,body websocket ping"


def test_search_github_issues_wraps_timeout_as_runtime_error():
    fake_client = FakeHTTPClient(exc=httpx.TimeoutException("timed out"))
    with pytest.raises(RuntimeError, match="timed out"):
        search_github_issues("anything", http_client=fake_client)


def test_search_github_issues_wraps_connection_failure_as_runtime_error():
    fake_client = FakeHTTPClient(exc=httpx.ConnectError("no route"))
    with pytest.raises(RuntimeError, match="Could not reach"):
        search_github_issues("anything", http_client=fake_client)


# ---- Agent.run -- tool-use loop mechanics --------------------------------

def test_agent_returns_final_answer_when_no_tool_is_needed():
    client = FakeAnthropicClient([
        FakeResponse([FakeTextBlock("FastAPI is a Python web framework.")], stop_reason="end_turn"),
    ])
    result = Agent(client=client).run("What is FastAPI?")
    assert result["answer"] == "FastAPI is a Python web framework."
    assert result["tools_used"] == []
    assert result["sources"] == []


def test_agent_executes_a_tool_and_feeds_the_result_back(monkeypatch):
    monkeypatch.setattr(
        agent_module, "search_github_issues",
        lambda query, limit=5, http_client=None: [{"number": 99, "title": "known bug", "state": "open", "labels": [], "url": "u"}],
    )
    client = FakeAnthropicClient([
        FakeResponse(
            [FakeToolUseBlock("search_github_issues", {"query": "websocket ping timeout"})],
            stop_reason="tool_use",
        ),
        FakeResponse([FakeTextBlock("Yes, that's tracked in issue #99.")], stop_reason="end_turn"),
    ])
    result = Agent(client=client).run("Is the websocket ping timeout a known bug?")
    assert result["answer"] == "Yes, that's tracked in issue #99."
    assert result["tools_used"] == ["search_github_issues"]
    # second messages.create() call must carry the tool result back to the model
    second_call_messages = client.messages.calls[1]["messages"]
    assert second_call_messages[-1]["content"][0]["tool_use_id"] == "tool_1"


def test_agent_marks_an_unknown_tool_as_a_tool_error_without_crashing(monkeypatch):
    client = FakeAnthropicClient([
        FakeResponse([FakeToolUseBlock("delete_production_database", {})], stop_reason="tool_use"),
        FakeResponse([FakeTextBlock("I can't do that, so here's what I can tell you instead.")], stop_reason="end_turn"),
    ])
    result = Agent(client=client).run("do something unsupported")
    assert result["answer"] == "I can't do that, so here's what I can tell you instead."
    tool_result = client.messages.calls[1]["messages"][-1]["content"][0]
    assert tool_result["is_error"] is True


def test_agent_gives_up_after_max_tool_iterations_instead_of_looping_forever(monkeypatch):
    # Never actually called (the loop should exhaust its iteration budget
    # before a 4th tool call), but stubbed so this test can't fall back to
    # a real, slow, network-dependent GitHub call if that assumption breaks.
    monkeypatch.setattr(agent_module, "search_github_issues", lambda query, limit=5, http_client=None: [])
    never_converges = [
        FakeResponse([FakeToolUseBlock("search_github_issues", {"query": "x"}, block_id=f"t{i}")], stop_reason="tool_use")
        for i in range(3)
    ]
    client = FakeAnthropicClient(never_converges)
    with pytest.raises(RuntimeError, match="did not reach a final answer"):
        Agent(client=client).run("loop forever", max_tool_iterations=3)


# ---- Agent.run -- Phase 02 tools (escalation, gap logging) ----------------

def test_agent_escalates_to_a_human_and_returns_the_booking():
    calendar_client = FakeCalendarClient()
    client = FakeAnthropicClient([
        FakeResponse(
            [FakeToolUseBlock("escalate_to_human", {"reason": "user needs a live walkthrough of dependency overrides"})],
            stop_reason="tool_use",
        ),
        FakeResponse([FakeTextBlock("I've booked time with the team for this.")], stop_reason="end_turn"),
    ])
    result = Agent(client=client, calendar_client=calendar_client).run("Can I talk to someone about this?")

    assert result["tools_used"] == ["escalate_to_human"]
    assert calendar_client.calls[0]["reason"] == "user needs a live walkthrough of dependency overrides"
    tool_result_content = client.messages.calls[1]["messages"][-1]["content"][0]["content"]
    assert "evt_1" in tool_result_content


def test_agent_logs_the_original_question_not_a_model_paraphrase():
    sheets_client = FakeSheetsClient()
    client = FakeAnthropicClient([
        FakeResponse(
            [FakeToolUseBlock("log_question_for_review", {"category": "missing-docs", "answered": False})],
            stop_reason="tool_use",
        ),
        FakeResponse([FakeTextBlock("I couldn't find anything on that in the docs.")], stop_reason="end_turn"),
    ])
    result = Agent(client=client, sheets_client=sheets_client).run("Does FastAPI support gRPC natively?")

    assert result["tools_used"] == ["log_question_for_review"]
    logged = sheets_client.calls[0]
    assert logged["question"] == "Does FastAPI support gRPC natively?"
    assert logged["category"] == "missing-docs"
    assert logged["answered"] is False


# ---- _next_escalation_slot --------------------------------------------------

def test_next_escalation_slot_rounds_up_to_the_next_half_hour(monkeypatch):
    monkeypatch.setattr(agent_module.dt, "datetime", FixedDatetime)
    # fixed "now" is 14:47 UTC, +60min lead = 15:47 -> rounds up to 16:00
    assert _next_escalation_slot() == dt.datetime(2026, 8, 20, 16, 0, tzinfo=dt.timezone.utc)


def test_next_escalation_slot_leaves_an_already_clean_half_hour_alone(monkeypatch):
    class ExactlyOnTheHour(FixedDatetime):
        fixed_now = dt.datetime(2026, 8, 20, 14, 0, tzinfo=dt.timezone.utc)

    monkeypatch.setattr(agent_module.dt, "datetime", ExactlyOnTheHour)
    # +60min lead = 15:00 exactly, already clean
    assert _next_escalation_slot() == dt.datetime(2026, 8, 20, 15, 0, tzinfo=dt.timezone.utc)


def test_next_escalation_slot_rolls_over_to_the_next_day(monkeypatch):
    class LateNight(FixedDatetime):
        fixed_now = dt.datetime(2026, 8, 20, 23, 50, tzinfo=dt.timezone.utc)

    monkeypatch.setattr(agent_module.dt, "datetime", LateNight)
    # +60min lead = 2026-08-21 00:50 -> rounds up to 01:00 the next day
    assert _next_escalation_slot() == dt.datetime(2026, 8, 21, 1, 0, tzinfo=dt.timezone.utc)


# ---- Phase 03: retry/backoff around the Claude API call --------------------

def test_agent_retries_a_rate_limited_call_and_succeeds():
    sleep = RecordingSleep()
    client = FakeAnthropicClient([
        make_api_status_error(429, "rate limited"),
        FakeResponse([FakeTextBlock("Here's the answer.")], stop_reason="end_turn"),
    ])
    result = Agent(client=client, sleep_fn=sleep).run("What is FastAPI?")
    assert result["answer"] == "Here's the answer."
    assert len(client.messages.calls) == 2
    assert sleep.delays == [1.0]


def test_agent_retries_on_a_connection_error():
    sleep = RecordingSleep()
    client = FakeAnthropicClient([
        make_connection_error(),
        FakeResponse([FakeTextBlock("Here's the answer.")], stop_reason="end_turn"),
    ])
    result = Agent(client=client, sleep_fn=sleep).run("What is FastAPI?")
    assert result["answer"] == "Here's the answer."


def test_agent_backoff_delay_doubles_on_each_retry():
    sleep = RecordingSleep()
    client = FakeAnthropicClient([
        make_api_status_error(503, "overloaded"),
        make_api_status_error(503, "overloaded"),
        FakeResponse([FakeTextBlock("Recovered.")], stop_reason="end_turn"),
    ])
    Agent(client=client, sleep_fn=sleep).run("anything")
    assert sleep.delays == [1.0, 2.0]


def test_agent_gives_up_after_max_retries_on_a_persistent_server_error():
    sleep = RecordingSleep()
    client = FakeAnthropicClient([
        make_api_status_error(503, "overloaded"),
        make_api_status_error(503, "overloaded"),
        make_api_status_error(503, "overloaded"),
    ])
    with pytest.raises(RuntimeError, match="status 503"):
        Agent(client=client, sleep_fn=sleep).run("anything")
    assert len(client.messages.calls) == 3
    assert sleep.delays == [1.0, 2.0]  # no sleep after the final, exhausted attempt


def test_agent_does_not_retry_a_client_error():
    sleep = RecordingSleep()
    client = FakeAnthropicClient([make_api_status_error(400, "bad request")])
    with pytest.raises(RuntimeError, match="status 400"):
        Agent(client=client, sleep_fn=sleep).run("anything")
    assert len(client.messages.calls) == 1
    assert sleep.delays == []


# ---- Phase 03: tool-input validation ---------------------------------------

def test_validate_tool_input_raises_on_missing_required_field():
    with pytest.raises(ValueError, match="missing required field"):
        _validate_tool_input("search_fastapi_docs", {})


def test_validate_tool_input_raises_on_wrong_type():
    with pytest.raises(ValueError, match="must be a boolean"):
        _validate_tool_input("log_question_for_review", {"category": "other", "answered": "yes"})


def test_validate_tool_input_raises_on_invalid_enum_value():
    with pytest.raises(ValueError, match="must be one of"):
        _validate_tool_input("log_question_for_review", {"category": "not-a-real-category", "answered": True})


def test_validate_tool_input_raises_on_unknown_tool():
    with pytest.raises(ValueError, match="Unknown tool"):
        _validate_tool_input("delete_everything", {})


def test_validate_tool_input_accepts_a_well_formed_call():
    _validate_tool_input("log_question_for_review", {"category": "missing-docs", "answered": False})  # no raise


def test_agent_turns_a_malformed_tool_call_into_a_tool_error_instead_of_crashing():
    # escalate_to_human with no "reason" -- before Phase 03 this hit
    # tool_input["reason"] inside _execute_tool and raised an uncaught
    # KeyError, which the run() except clause didn't catch, crashing the
    # whole request instead of letting the model see and correct its call.
    client = FakeAnthropicClient([
        FakeResponse([FakeToolUseBlock("escalate_to_human", {})], stop_reason="tool_use"),
        FakeResponse([FakeTextBlock("Let me try that again properly.")], stop_reason="end_turn"),
    ])
    result = Agent(client=client).run("can I talk to someone?")
    assert result["answer"] == "Let me try that again properly."
    tool_result = client.messages.calls[1]["messages"][-1]["content"][0]
    assert tool_result["is_error"] is True
    assert "missing required field" in tool_result["content"]


# ---- Agent.run -- Phase 05 token accounting --------------------------------

def test_agent_reports_token_usage_for_a_single_call_answer():
    client = FakeAnthropicClient([
        FakeResponse([FakeTextBlock("FastAPI is a Python web framework.")], stop_reason="end_turn",
                     input_tokens=42, output_tokens=17),
    ])
    result = Agent(client=client).run("What is FastAPI?")
    assert result["input_tokens"] == 42
    assert result["output_tokens"] == 17


def test_agent_sums_token_usage_across_every_call_in_a_tool_use_round_trip(monkeypatch):
    monkeypatch.setattr(agent_module, "search_github_issues", lambda query, limit=5, http_client=None: [])
    client = FakeAnthropicClient([
        FakeResponse([FakeToolUseBlock("search_github_issues", {"query": "x"})], stop_reason="tool_use",
                     input_tokens=100, output_tokens=20),
        FakeResponse([FakeTextBlock("Nothing found.")], stop_reason="end_turn",
                     input_tokens=130, output_tokens=8),
    ])
    result = Agent(client=client).run("is x a known bug?")
    # a tool-use round trip is 2 API calls -- the total is what costs money,
    # not just whichever call happened to be last
    assert result["input_tokens"] == 100 + 130
    assert result["output_tokens"] == 20 + 8

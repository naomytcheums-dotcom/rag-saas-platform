"""
Unit tests for src/observability.py.

TelemetryStore is exercised against a real temp file (tmp_path) rather
than mocked -- it's a thin, three-method file wrapper, and testing the
actual read/write round-trip is more honest than mocking `open()`. The
aggregate functions (percentile, cost, error rate, tool counts) are pure
and tested directly against hand-built record lists. record_run() is
tested against a fake agent, same pattern as test_agent_evaluation.py's
FakeAgent -- no live Anthropic call anywhere here.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from observability import (  # noqa: E402
    TelemetryStore,
    error_rate,
    latency_summary,
    record_run,
    tool_usage_counts,
    total_cost_usd,
)


class FakeAgent:
    def __init__(self, responses):
        self._responses = responses

    def run(self, question):
        outcome = self._responses[question]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


# ---- TelemetryStore -------------------------------------------------------

def test_read_all_returns_empty_list_when_no_file_exists_yet(tmp_path):
    store = TelemetryStore(path=tmp_path / "telemetry.jsonl")
    assert store.read_all() == []


def test_append_then_read_all_round_trips_records_in_order(tmp_path):
    store = TelemetryStore(path=tmp_path / "telemetry.jsonl")
    store.append({"question": "first", "cost_usd": 0.01})
    store.append({"question": "second", "cost_usd": 0.02})
    records = store.read_all()
    assert [r["question"] for r in records] == ["first", "second"]


def test_append_creates_the_parent_directory_if_missing(tmp_path):
    store = TelemetryStore(path=tmp_path / "nested" / "telemetry.jsonl")
    store.append({"question": "q"})
    assert store.read_all() == [{"question": "q"}]


# ---- latency_summary (percentiles) -----------------------------------------

def test_latency_summary_on_one_hundred_evenly_spaced_values():
    records = [{"elapsed_ms": ms} for ms in range(10, 1001, 10)]  # 10, 20, ..., 1000
    summary = latency_summary(records)
    assert summary["count"] == 100
    assert summary["p50_ms"] == 500
    assert summary["p95_ms"] == 950


def test_latency_summary_on_a_single_record():
    assert latency_summary([{"elapsed_ms": 250}]) == {"count": 1, "p50_ms": 250, "p95_ms": 250}


def test_latency_summary_on_no_records():
    assert latency_summary([]) == {"count": 0, "p50_ms": 0.0, "p95_ms": 0.0}


# ---- total_cost_usd / error_rate / tool_usage_counts -----------------------

def test_total_cost_usd_sums_across_records():
    records = [{"cost_usd": 0.01}, {"cost_usd": 0.025}, {"cost_usd": 0.0}]
    assert total_cost_usd(records) == pytest.approx(0.035)


def test_error_rate_on_a_mix_of_success_and_failure():
    records = [{"success": True}, {"success": True}, {"success": False}, {"success": False}]
    assert error_rate(records) == 0.5


def test_error_rate_on_no_records_is_zero_not_a_division_error():
    assert error_rate([]) == 0.0


def test_tool_usage_counts_aggregates_across_records_and_within_one_record():
    records = [
        {"tools_used": ["search_fastapi_docs"]},
        {"tools_used": ["search_fastapi_docs", "search_github_issues"]},
        {"tools_used": []},
    ]
    assert tool_usage_counts(records) == {"search_fastapi_docs": 2, "search_github_issues": 1}


# ---- record_run ---------------------------------------------------------

def test_record_run_logs_a_successful_call_with_computed_cost(tmp_path):
    store = TelemetryStore(path=tmp_path / "telemetry.jsonl")
    agent = FakeAgent({
        "How do I use Depends?": {
            "answer": "stub", "tools_used": ["search_fastapi_docs"],
            "input_tokens": 1000, "output_tokens": 200, "elapsed_ms": 850,
        }
    })

    outcome = record_run(store, agent, "How do I use Depends?")

    assert outcome["answer"] == "stub"  # the real outcome is still returned to the caller
    logged = store.read_all()[0]
    assert logged["success"] is True
    assert logged["tools_used"] == ["search_fastapi_docs"]
    assert logged["cost_usd"] == pytest.approx((1000 * 3.0 + 200 * 15.0) / 1_000_000)


def test_record_run_logs_a_failed_call_and_still_raises(tmp_path):
    store = TelemetryStore(path=tmp_path / "telemetry.jsonl")
    agent = FakeAgent({"bad question": RuntimeError("Claude API call failed (status 500): overloaded")})

    with pytest.raises(RuntimeError, match="overloaded"):
        record_run(store, agent, "bad question")

    logged = store.read_all()[0]
    assert logged["success"] is False
    assert logged["cost_usd"] == 0.0
    assert logged["tools_used"] == []
    assert "overloaded" in logged["error"]

"""
Unit tests for src/agent_evaluation.py.

No live Anthropic call anywhere here -- run_evaluation() is exercised
against a fake agent that returns scripted tools_used lists (or raises,
to test the one-case-errors-without-killing-the-run path), same pattern
as test_agent.py's FakeAnthropicClient. Scoring a real Agent's actual
routing decisions needs live API credit -- see the module docstring.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agent_evaluation import load_eval_set, run_evaluation, score_case, summarize_by_category  # noqa: E402


class FakeAgent:
    """Maps a question to either a tools_used list (agent.run() succeeds)
    or an exception instance (agent.run() raises it)."""

    def __init__(self, responses):
        self._responses = responses

    def run(self, question):
        outcome = self._responses[question]
        if isinstance(outcome, Exception):
            raise outcome
        return {"answer": "stub", "tools_used": outcome, "sources": [], "elapsed_ms": 0}


# ---- load_eval_set -- sanity-check the real committed data file -----------

def test_the_real_eval_set_loads_and_has_no_duplicate_ids():
    cases = load_eval_set()
    assert len(cases) >= 10
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids))


def test_the_real_eval_set_covers_more_than_one_category():
    cases = load_eval_set()
    assert len({c["category"] for c in cases}) >= 3


def test_load_eval_set_rejects_duplicate_ids(tmp_path):
    bad_file = tmp_path / "dupes.json"
    bad_file.write_text(json.dumps([
        {"id": "x1", "category": "usage", "question": "q1", "expected_tools": []},
        {"id": "x1", "category": "usage", "question": "q2", "expected_tools": []},
    ]))
    with pytest.raises(ValueError, match="duplicate"):
        load_eval_set(bad_file)


# ---- score_case -------------------------------------------------------

def test_score_case_passes_on_an_exact_match():
    case = {"expected_tools": ["search_fastapi_docs"]}
    assert score_case(case, ["search_fastapi_docs"]) is True


def test_score_case_fails_when_an_expected_tool_is_missing():
    case = {"expected_tools": ["search_fastapi_docs", "search_github_issues"]}
    assert score_case(case, ["search_fastapi_docs"]) is False


def test_score_case_fails_on_an_unexpected_extra_tool():
    case = {"expected_tools": ["search_fastapi_docs"]}
    assert score_case(case, ["search_fastapi_docs", "search_github_issues"]) is False


def test_score_case_passes_when_no_tools_are_expected_and_none_were_used():
    case = {"expected_tools": []}
    assert score_case(case, []) is True


def test_score_case_ignores_call_order():
    case = {"expected_tools": ["search_fastapi_docs", "search_github_issues"]}
    assert score_case(case, ["search_github_issues", "search_fastapi_docs"]) is True


# ---- run_evaluation -----------------------------------------------------

def test_run_evaluation_scores_a_mix_of_passing_and_failing_cases():
    cases = [
        {"id": "c1", "category": "usage", "question": "q1", "expected_tools": ["search_fastapi_docs"]},
        {"id": "c2", "category": "known-issue", "question": "q2", "expected_tools": ["search_github_issues"]},
    ]
    agent = FakeAgent({
        "q1": ["search_fastapi_docs"],  # correct
        "q2": [],  # wrong -- expected search_github_issues
    })
    evaluation = run_evaluation(agent, cases)
    assert evaluation["total"] == 2
    assert evaluation["passed"] == 1
    assert evaluation["success_rate"] == 0.5


def test_run_evaluation_marks_an_errored_case_failed_without_stopping_the_rest():
    cases = [
        {"id": "c1", "category": "usage", "question": "q1", "expected_tools": ["search_fastapi_docs"]},
        {"id": "c2", "category": "usage", "question": "q2", "expected_tools": ["search_fastapi_docs"]},
    ]
    agent = FakeAgent({
        "q1": RuntimeError("Claude API call failed (status 500): overloaded"),
        "q2": ["search_fastapi_docs"],  # still gets scored even though c1 errored
    })
    evaluation = run_evaluation(agent, cases)
    assert evaluation["total"] == 2
    assert evaluation["passed"] == 1
    c1_result = next(r for r in evaluation["results"] if r["id"] == "c1")
    assert c1_result["passed"] is False
    assert "overloaded" in c1_result["error"]


def test_run_evaluation_defaults_to_the_real_committed_eval_set():
    class AlwaysEmptyAgent:
        def run(self, question):
            return {"answer": "", "tools_used": [], "sources": [], "elapsed_ms": 0}

    evaluation = run_evaluation(AlwaysEmptyAgent())
    assert evaluation["total"] == len(load_eval_set())


# ---- summarize_by_category --------------------------------------------

def test_summarize_by_category_aggregates_pass_rate_per_category():
    evaluation = {
        "results": [
            {"category": "usage", "passed": True},
            {"category": "usage", "passed": False},
            {"category": "known-issue", "passed": True},
        ]
    }
    summary = summarize_by_category(evaluation)
    assert summary["usage"] == {"total": 2, "passed": 1, "success_rate": 0.5}
    assert summary["known-issue"] == {"total": 1, "passed": 1, "success_rate": 1.0}

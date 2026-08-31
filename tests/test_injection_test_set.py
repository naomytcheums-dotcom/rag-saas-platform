"""
Tests for data/injection_test_set.json and src/injection_tests.py.

The actual checking logic (check_case / run_suite) now lives in
agentfixture (https://github.com/naomytcheums-dotcom/agentfixture) and
is tested there -- re-testing it here would just duplicate agentfixture's
own suite across two repos. What's Nova-specific, and what stays here:

1. The test set's own structure -- catches a malformed or vacuous case
   (no id, unknown category, nothing it actually checks) before it ever
   gets run against a real agent.
2. That src/injection_tests.py correctly wires load_cases() into
   agentfixture.run_suite -- a thin integration test, not a re-test of
   agentfixture's internals.

Whether the *agent itself* resists these attacks is NOT tested here --
that needs a live Agent() and Anthropic credit, same gap as everywhere
else in this project. Run `python src/injection_tests.py` once credit is
available.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from injection_tests import DATA_PATH, load_cases, run_suite  # noqa: E402


# ---- structure of data/injection_test_set.json -----------------------------

def test_data_file_is_valid_json_with_cases():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    assert isinstance(data["cases"], list)
    assert len(data["cases"]) >= 10  # a handful of cases isn't a "suite"


def test_every_case_has_a_unique_id():
    cases = load_cases()
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids))


def test_every_case_uses_a_declared_category():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    declared = set(data["categories"])
    for case in data["cases"]:
        assert case["category"] in declared, f"{case['id']} uses an undeclared category {case['category']!r}"


def test_every_case_has_a_non_empty_prompt():
    for case in load_cases():
        assert isinstance(case["prompt"], str) and case["prompt"].strip()


def test_every_case_actually_checks_something():
    # A case with no forbidden_phrases, no forbidden_tools, and no
    # max_tool_calls would always "pass" regardless of what the agent
    # does -- silently useless.
    for case in load_cases():
        has_a_check = bool(
            case.get("forbidden_phrases")
            or case.get("forbidden_tools")
            or case.get("max_tool_calls")
        )
        assert has_a_check, f"{case['id']} has no assertion to actually check"


# ---- run_suite() wiring, against a fake agent -----------------------------

class ScriptedAgent:
    """Fake Agent -- .run(prompt) returns from a dict keyed by prompt, or
    raises if the scripted value is an exception instance."""

    def __init__(self, by_prompt):
        self._by_prompt = by_prompt

    def run(self, prompt):
        outcome = self._by_prompt.get(prompt)
        if isinstance(outcome, BaseException):
            raise outcome
        if outcome is None:
            raise AssertionError(f"ScriptedAgent has no scripted outcome for prompt: {prompt!r}")
        return outcome


def test_run_suite_marks_every_case_failed_when_the_agent_run_itself_errors():
    cases = load_cases()
    by_prompt = {case["prompt"]: RuntimeError("Claude API call failed (status 503): overloaded") for case in cases}
    summary = run_suite(agent=ScriptedAgent(by_prompt))
    assert summary["passed"] == 0
    assert summary["total"] == len(cases)
    assert all("overloaded" in r["error"] for r in summary["results"])


def test_run_suite_marks_every_case_passed_when_the_agent_resists_the_attack():
    cases = load_cases()
    # A bland, on-topic, tool-free answer satisfies every case's checks in
    # this test set (none of the forbidden_phrases appear, and no
    # forbidden/over-called tool) -- proving a clean run reports all-passed.
    by_prompt = {
        case["prompt"]: {"answer": "I can only help with FastAPI documentation questions.", "tools_used": []}
        for case in cases
    }
    summary = run_suite(agent=ScriptedAgent(by_prompt))
    assert summary["passed"] == summary["total"] == len(cases)
    assert summary["resistance_rate"] == 1.0

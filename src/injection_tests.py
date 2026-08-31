"""
Phase 03: prompt-injection / jailbreak resistance suite.

Loads data/injection_test_set.json and runs each case against a live
Agent, checking the response against `forbidden_phrases` (a hit means
the attack likely worked), `forbidden_tools`, and `max_tool_calls`.

The checking logic itself now lives in agentfixture (this project's own
generalized-and-extracted test library, see
https://github.com/naomytcheums-dotcom/agentfixture) -- this file is
Nova-specific glue: loading the data file and giving it Nova's CLI.

Needs Anthropic API credit to run for real -- same untested-live gap as
generation.py, llm_judge.py, and hallucination_detection.py (see
AUDIT.md / README's "Current limitations"). What IS tested without credit
is the test set's own structure and, via agentfixture's own test suite,
the checking logic itself -- see tests/test_injection_test_set.py.
"""

import argparse
import json
from pathlib import Path

from agentfixture import run_suite as _run_suite

from agent import Agent

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "injection_test_set.json"


def load_cases():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return data["cases"]


def run_suite(agent=None):
    """Runs every case against `agent` (a live Agent() if not given, or
    anything with a matching .run(prompt) for tests) via
    agentfixture.run_suite, and returns its summary dict: {"total",
    "passed", "resistance_rate", "results": [{"id", "category",
    "passed", "violations", "error"}, ...]}."""
    agent = agent if agent is not None else Agent()
    return _run_suite(agent, load_cases())


def main():
    parser = argparse.ArgumentParser(description="Run the prompt-injection resistance suite against a live agent.")
    parser.parse_args()

    try:
        summary = run_suite()
    except EnvironmentError as exc:
        raise SystemExit(f"Cannot run the injection suite: {exc}")

    print(f"\n{summary['passed']}/{summary['total']} cases passed ({summary['resistance_rate']:.0%})\n")
    for result in summary["results"]:
        status = "PASS" if result["passed"] else "FAIL"
        print(f"[{status}] {result['id']}")
        for violation in result["violations"]:
            print(f"       -- {violation}")
        if result["error"]:
            print(f"       -- agent run failed: {result['error']}")

    if summary["passed"] < summary["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

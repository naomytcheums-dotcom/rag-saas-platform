"""
Phase 04: measures whether the agent picks the *right* tools for a
question, not just whether it produces an answer. Complements
evaluation.py (which scores retrieval quality in isolation) with a
routing-accuracy metric specific to the agentic layer -- the number that
actually matters once the pipeline can call tools, since a confident
wrong answer from the wrong source is worse than a slow correct one.

Scope: data/agent_eval_set.json only exercises the two read-only search
tools' routing (docs vs. GitHub vs. neither vs. both) -- escalate_to_human
and log_question_for_review are judgment calls about an answer's quality,
not a routing decision with one correct target, so they're out of scope
for an exact-match harness like this one.

Needs live Anthropic credit to run against a real Agent -- same gap as
generation.py and the injection test set (see README). What's tested
without credit, in tests/test_agent_evaluation.py, is the harness itself:
given a case's expected tools and a recorded set of tools actually used,
does it score correctly, and does one case erroring stop it from scoring
the rest.
"""

import argparse
import json
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVAL_SET_PATH = PROJECT_ROOT / "data" / "agent_eval_set.json"

logger = logging.getLogger(__name__)


def load_eval_set(path=DEFAULT_EVAL_SET_PATH):
    with open(path, encoding="utf-8") as f:
        cases = json.load(f)
    ids = [case["id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("agent_eval_set.json has duplicate case ids")
    return cases


def score_case(case, actual_tools_used):
    """Exact-set match: the agent must call precisely the expected tools --
    no fewer (a missing search means it answered on knowledge it had no
    business relying on) and no more (over-calling burns cost and latency
    for no benefit on a question that didn't need it)."""
    return set(case["expected_tools"]) == set(actual_tools_used)


def run_evaluation(agent, cases=None):
    cases = cases if cases is not None else load_eval_set()
    results = []
    for case in cases:
        try:
            outcome = agent.run(case["question"])
            results.append({
                "id": case["id"],
                "category": case["category"],
                "passed": score_case(case, outcome["tools_used"]),
                "expected_tools": case["expected_tools"],
                "actual_tools": outcome["tools_used"],
                "error": None,
            })
        except RuntimeError as exc:
            # One case failing to even run (API error, retry exhaustion)
            # shouldn't stop the rest of the set from being scored --
            # score it as failed and keep going.
            logger.warning("eval case %s errored instead of returning: %s", case["id"], exc)
            results.append({
                "id": case["id"],
                "category": case["category"],
                "passed": False,
                "expected_tools": case["expected_tools"],
                "actual_tools": None,
                "error": str(exc),
            })

    passed = sum(1 for r in results if r["passed"])
    return {
        "total": len(results),
        "passed": passed,
        "success_rate": passed / len(results) if results else 0.0,
        "results": results,
    }


def summarize_by_category(evaluation):
    """Aggregate pass rate per category -- a single overall number hides
    whether failures cluster in one kind of question (e.g. the agent is
    fine on usage questions but never learns to check GitHub)."""
    by_category = {}
    for result in evaluation["results"]:
        bucket = by_category.setdefault(result["category"], {"total": 0, "passed": 0})
        bucket["total"] += 1
        bucket["passed"] += int(result["passed"])
    return {
        category: {**counts, "success_rate": counts["passed"] / counts["total"]}
        for category, counts in by_category.items()
    }


def main():
    from agent import Agent

    parser = argparse.ArgumentParser(description="Score the agent's tool-routing accuracy against the labeled eval set.")
    parser.add_argument("--eval-set", default=DEFAULT_EVAL_SET_PATH)
    args = parser.parse_args()

    try:
        agent = Agent()
    except EnvironmentError as exc:
        raise SystemExit(f"Could not start the agent: {exc}")

    cases = load_eval_set(args.eval_set)
    evaluation = run_evaluation(agent, cases)

    print(f"\n{evaluation['passed']}/{evaluation['total']} cases correctly routed "
          f"({evaluation['success_rate']:.0%})\n")
    for category, stats in summarize_by_category(evaluation).items():
        print(f"  {category:<14} {stats['passed']}/{stats['total']} ({stats['success_rate']:.0%})")

    print("\nMisses:")
    for result in evaluation["results"]:
        if not result["passed"]:
            print(f"  [{result['id']}] expected {result['expected_tools']}, "
                  f"got {result['actual_tools']}" + (f" (error: {result['error']})" if result["error"] else ""))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    main()

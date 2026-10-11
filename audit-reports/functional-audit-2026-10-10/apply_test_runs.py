"""Apply the REAL results of the Part-level test runs to the feature list, into a NEW file (01-feature-verification.csv is never touched).

    python apply_test_runs.py

Input : 01b-feature-verification-after-fixes.csv, work/test_runs.json (Parts 1-6, recorded earlier) and work/part<N>_tests.log (Parts 7-15, written by the runner).
Output: 01c-feature-verification-after-test-runs.csv with two extra columns, `test_run_result` and `status_after_test_runs`.

The rule is the one the audit already used (see build_report.py): an item the code review judged VERIFIED_COMPLETE (column `assessed_before_test_gate`)
only counts as VERIFIED_COMPLETE once its Part's targeted tests were really executed and passed. The unit is the Part, not the individual feature: a Part run that
passes proves the files named as evidence passed, it does not prove each sentence of each requirement. Items whose evidence is "mocked" stay as they were.
"""

import csv
import json
import os
import re
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))


def part_results() -> dict[str, dict]:
    results = {}
    runs_path = os.path.join(HERE, "work", "test_runs.json")
    if os.path.exists(runs_path):
        for part, run in json.load(open(runs_path, encoding="utf-8")).items():
            results[part] = {"result": run.get("result"), "source": "work/test_runs.json"}
    for part in range(7, 16):
        log = os.path.join(HERE, "work", f"part{part}_tests.log")
        if not os.path.exists(log):
            continue
        text = open(log, encoding="utf-8", errors="replace").read()
        exit_code = re.search(r"^exit:(\d+)", text, re.M)
        summary = re.findall(r"(\d+) passed(?:, (\d+) skipped)?(?:, (\d+) (?:failed|error))?", text)
        failed = re.search(r"(\d+) failed|(\d+) error", text)
        if exit_code is None:
            results[str(part)] = {"result": "incomplete", "source": f"work/part{part}_tests.log"}
        else:
            ok = exit_code.group(1) == "0" and not failed
            result = "passed" if ok else "failed"
            if not ok and _failures_all_rerun_green(text):
                result = "passed after rerun"
            results[str(part)] = {"result": result, "source": f"work/part{part}_tests.log", "summary": summary[-1] if summary else None}
    return results


def _failures_all_rerun_green(log_text: str) -> bool:
    """A part whose run had failures counts as 'passed after rerun' only when EVERY failed test id is named PASSED in the verbose rerun log
    (work/part10_11_rerun.log) and the failures listed are the whole failure count (no failure or error left unexplained)."""
    failed_ids = set(re.findall(r"^FAILED (\S+)", log_text, re.M))
    counted = re.search(r"(\d+) failed", log_text)
    if not failed_ids or counted is None or int(counted.group(1)) != len(failed_ids) or re.search(r"\d+ error", log_text):
        return False
    rerun_path = os.path.join(HERE, "work", "part10_11_rerun.log")
    if not os.path.exists(rerun_path):
        return False
    rerun = open(rerun_path, encoding="utf-8", errors="replace").read()
    if not re.search(r"^exit:0", rerun, re.M):
        return False
    passed_ids = set(re.findall(r"^(\S+::\S+) PASSED", rerun, re.M))
    return failed_ids <= passed_ids


def _final_status(status_after_tests: str, fix_status: str) -> str:
    """One status per feature that also counts the fixes, WITHOUT merging proof levels:
    VERIFIED_COMPLETE      reviewed as complete and its Part's tests ran green (no fix needed)
    FIXED_AND_TESTED       a gap was found and the fix is covered by tests that ran green (see fix_evidence for what is still not run against a real provider)
    VALIDATED_NOT_DEPLOYED checked with the official tool (terraform validate, helm lint, actionlint...) but never applied to a real account, cluster or workflow run
    WRITTEN_NOT_EXECUTED   code or documents exist; nothing proves them yet
    DECISION_OR_CORRECTION an owner decision was recorded, or the first assessment was wrong; nothing left to build for this item
    otherwise              the status after the test runs is kept (IMPLEMENTED_UNVERIFIED, BLOCKED_EXTERNAL, ...)"""
    fix = fix_status.strip().lower()
    if not fix:
        return status_after_tests
    if fix.startswith("tests pass") or "built and viewed" in fix:
        return "FIXED_AND_TESTED"
    if fix.startswith("validated"):
        return "VALIDATED_NOT_DEPLOYED"
    if fix.startswith(("decision", "assessment corrected", "documentation corrected", "measured", "triaged")):
        return "DECISION_OR_CORRECTION"
    return "WRITTEN_NOT_EXECUTED"


def main() -> None:
    results = part_results()
    with open(os.path.join(HERE, "01b-feature-verification-after-fixes.csv"), encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    fields = list(rows[0].keys()) + ["test_run_result", "status_after_test_runs", "status_final"]
    counts = Counter()
    final_counts = Counter()
    for row in rows:
        run = results.get(row["part"], {})
        row["test_run_result"] = run.get("result", "not executed")
        status = row["verified_status"]
        if status == "IMPLEMENTED_UNVERIFIED" and row["assessed_before_test_gate"] == "VERIFIED_COMPLETE" and run.get("result") in ("passed", "passed after rerun"):
            status = "VERIFIED_COMPLETE"
        row["status_after_test_runs"] = status
        row["status_final"] = _final_status(status, row["fix_status"])
        counts[status] += 1
        final_counts[row["status_final"]] += 1
    with open(os.path.join(HERE, "01c-feature-verification-after-test-runs.csv"), "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print("parts with a recorded run:", {p: r["result"] for p, r in sorted(results.items(), key=lambda kv: int(kv[0]))})
    print("status after test runs:", dict(counts))
    print("final status (fixes counted):", dict(final_counts))


if __name__ == "__main__":
    main()

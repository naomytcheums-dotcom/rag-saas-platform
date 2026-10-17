"""Spec 15.2.7: the benchmark -> improvement cycle (scripts/continuous_improvement_cycle.py), on the real measurement committed in docs/project-handover/e2e_evidence/."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import continuous_improvement_cycle as cycle  # noqa: E402

BASELINE = ROOT / "docs" / "project-handover" / "e2e_evidence" / "retrieval_baseline.json"


@pytest.fixture
def baseline():
    return cycle.load(BASELINE)


def test_the_real_baseline_is_judged_by_the_guardian_thresholds_not_flattered(baseline):
    result = cycle.verdict(baseline, baseline, tolerance=0.02, min_gain=0.03)
    default = baseline["report"][result["default_config"]]["all"]
    assert result["default_config"].startswith("hybrid | default")
    assert default["recall@10"] < 0.75 and result["exit_code"] == cycle.CRITICAL  # the committed default is genuinely below the critical line
    levels = {f["metric"]: f["level"] for f in result["guardian"]}
    assert levels["recall@10"] == "critical" and levels["mrr"] == "critical" and levels["recall@5"] == "warning"
    assert result["regressions"] == []  # a measurement never regresses against itself


def test_a_candidate_must_win_on_mrr_without_losing_recall_and_is_checked_on_the_held_out_split(baseline):
    result = cycle.verdict(baseline, baseline, tolerance=0.02, min_gain=0.03)
    by_name = {c["config"]: c for c in result["candidates"]}
    assert result["candidates"][0]["mrr_gain"] >= result["candidates"][-1]["mrr_gain"]
    assert by_name["hybrid + multi-query | no threshold, top_k 10"]["confirmed_on_held_out"] is True
    assert by_name["hybrid_reranked | no threshold, top_k 10"]["confirmed_on_held_out"] is False  # better overall, worse on the held-out questions
    assert all(c["recall@10"] >= baseline["report"][result["default_config"]]["all"]["recall@10"] for c in result["candidates"])
    assert "bm25_only | default (threshold 0.5, top_k 5)" not in by_name  # worse than the default: never proposed


def test_a_drop_beyond_the_tolerance_is_a_regression_and_a_small_one_is_not(baseline):
    current = copy.deepcopy(baseline)
    name = next(iter(current["report"]))
    current["report"][name]["all"]["recall@5"] -= 0.05
    current["report"][name]["all"]["mrr"] -= 0.01
    found = cycle.regressions(current, baseline, tolerance=0.02)
    assert [(r["config"], r["metric"]) for r in found] == [(name, "recall@5")]
    assert found[0]["delta"] == pytest.approx(-0.05)
    assert cycle.verdict(current, baseline, 0.02, 0.03)["exit_code"] >= cycle.WARNING


def test_a_healthy_measurement_exits_zero():
    healthy = {"corpus": "x", "questions": 1, "report": {"hybrid | default": {"all": {"recall@1": 0.9, "recall@5": 0.95, "recall@10": 0.97, "mrr": 0.9, "ndcg@10": 0.9}}}}
    result = cycle.verdict(healthy, healthy, 0.02, 0.03)
    assert result["exit_code"] == cycle.OK and result["candidates"] == [] and all(f["level"] == "ok" for f in result["guardian"])


@pytest.mark.parametrize("value, level", [(0.69, "critical"), (0.70, "warning"), (0.79, "warning"), (0.80, "ok")])
def test_the_recall_at_5_thresholds_are_the_ones_of_agents_md(value, level):
    assert {f["metric"]: f["level"] for f in cycle.guardian({"recall@5": value})}["recall@5"] == level


def test_the_report_and_json_are_written_and_the_table_survives_pipes_in_names(tmp_path, capsys, baseline):
    argv = ["x", "compare", "--current", str(BASELINE), "--baseline", str(BASELINE), "--report-dir", str(tmp_path), "--label", "2026-10-13"]
    old = sys.argv
    sys.argv = argv
    try:
        assert cycle.main() == cycle.CRITICAL
    finally:
        sys.argv = old
    markdown = (tmp_path / "2026-10-13.md").read_text(encoding="utf-8")
    assert "# Improvement cycle 2026-10-13" in markdown and "**CRITICAL**" in markdown and "multi-query" in markdown
    table = [line for line in markdown.splitlines() if line.startswith("| hybrid")]
    assert table and all(line.count("|") == 8 for line in table), table  # 7 columns: a '|' inside a name would add one
    assert json.loads((tmp_path / "2026-10-13.json").read_text(encoding="utf-8"))["exit_code"] == 2


def test_a_file_that_is_not_a_measurement_is_refused(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"hello": 1}), encoding="utf-8")
    with pytest.raises(ValueError, match="not a retrieval measurement"):
        cycle.load(bad)


def test_run_refuses_a_non_local_api():
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "continuous_improvement_cycle.py"), "run", "--base", "https://api.example.com"], capture_output=True, text=True, check=False)
    assert result.returncode != 0 and "REFUSED" in (result.stderr + result.stdout)


def test_the_scheduled_workflow_runs_the_cycle_on_a_disposable_stack_without_secrets():
    import yaml

    text = (ROOT / ".github" / "workflows" / "continuous-improvement.yml").read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)
    triggers = workflow.get("on") or workflow[True]  # YAML 1.1 reads the key `on` as the boolean True
    assert triggers["schedule"][0]["cron"] and "workflow_dispatch" in triggers
    job = workflow["jobs"]["cycle"]
    assert {"postgres", "redis"} <= set(job["services"])
    import re

    assert not re.search(r"\$\{\{\s*secrets\.", text), "the cycle must run on throw-away values only"
    assert "continuous_improvement_cycle.py run" in text and "--no-llm" in text and "continuous_improvement_cycle.py compare" in text
    assert workflow["permissions"] == {"contents": "read", "issues": "write"}
    assert "gh issue create" in text and "git push" not in text and "gh pr" not in text, "the workflow proposes, it never changes code"

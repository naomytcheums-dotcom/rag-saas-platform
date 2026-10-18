"""One turn of the continuous-improvement loop (spec 15.2.7, benchmark -> improvement): measure, compare with the committed baseline, decide, report.

    # 1. measure on the real corpus (155 FastAPI documentation pages, 50 questions with a known source page) against a LOCAL stack
    python scripts/continuous_improvement_cycle.py run --base http://127.0.0.1:8010 --run-out run.json
    # 2. compare a run with the baseline and write the dated report (exit 0 healthy, 1 warning or regression, 2 critical)
    python scripts/continuous_improvement_cycle.py compare --current run.json --baseline docs/project-handover/e2e_evidence/retrieval_baseline.json \
        --report-dir docs/operations/improvement

`run` registers a throw-away account on the local API, uploads the corpus, waits for the worker to index it, then calls scripts/measure_retrieval_baseline.py
(the production retrieval code, no answer generation, no paid service). `compare` is pure: it reads two JSON files.

What the verdict means:
  * GUARDIAN thresholds (agents.md, section 2) on the default configuration: Recall@5 < 0.80 warning / < 0.70 critical, Recall@10 < 0.85 / 0.75, MRR < 0.75 / 0.65,
    NDCG < 0.70 / 0.60. The committed baseline is itself below some of them: the report says so instead of hiding it.
  * REGRESSION: a metric of a configuration dropped by more than --tolerance (default 0.02) against the baseline.
  * IMPROVEMENT CANDIDATE: another configuration beats the default by at least --min-gain (default 0.03) on MRR and does not lose on Recall@10: the report proposes switching the
    default to it. A candidate is a proposal: it must be applied on a branch, re-measured and merged by a human (agents.md, CHANGELAB), never applied by this script.
The held-out questions (the `held_out` split) are reported separately so a candidate is judged on questions nobody tuned on."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# agents.md section 2 (GUARDIAN): metric -> (warning below, critical below)
THRESHOLDS = {"recall@5": (0.80, 0.70), "recall@10": (0.85, 0.75), "mrr": (0.75, 0.65), "ndcg@10": (0.70, 0.60)}
DEFAULT_CONFIG_HINT = "hybrid | default"
OK, WARNING, CRITICAL = 0, 1, 2


def load(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if "report" not in data or not isinstance(data["report"], dict) or not data["report"]:
        raise ValueError(f"{path}: not a retrieval measurement (no `report`)")
    return data


def default_config(report: dict) -> str:
    for name in report:
        if name.lower().startswith(DEFAULT_CONFIG_HINT):
            return name
    return next(iter(report))


def guardian(metrics: dict[str, float]) -> list[dict]:
    findings = []
    for metric, (warn, crit) in THRESHOLDS.items():
        value = metrics.get(metric)
        if value is None:
            continue
        level = "critical" if value < crit else "warning" if value < warn else "ok"
        findings.append({"metric": metric, "value": value, "warning_below": warn, "critical_below": crit, "level": level})
    return findings


def regressions(current: dict, baseline: dict, tolerance: float) -> list[dict]:
    found = []
    for name, cur in current["report"].items():
        base = baseline["report"].get(name)
        if not base:
            continue
        for metric in THRESHOLDS:
            new, old = cur.get("all", {}).get(metric), base.get("all", {}).get(metric)
            if new is not None and old is not None and new < old - tolerance:
                found.append({"config": name, "metric": metric, "baseline": old, "current": new, "delta": round(new - old, 3)})
    return found


def candidates(current: dict, min_gain: float) -> list[dict]:
    report = current["report"]
    default = default_config(report)
    base = report[default]["all"]
    ranked = []
    for name, entry in report.items():
        if name == default:
            continue
        cur = entry.get("all", {})
        gain = round(cur.get("mrr", 0.0) - base.get("mrr", 0.0), 3)
        loses = cur.get("recall@10", 0.0) < base.get("recall@10", 0.0) - 1e-9
        held = entry.get("held_out", {})
        held_base = report[default].get("held_out", {})
        held_gain = round(held.get("mrr", 0.0) - held_base.get("mrr", 0.0), 3) if held and held_base else None
        if gain >= min_gain and not loses:
            ranked.append({"config": name, "mrr_gain": gain, "recall@10": cur.get("recall@10"), "held_out_mrr_gain": held_gain,
                           "confirmed_on_held_out": held_gain is not None and held_gain > 0})
    return sorted(ranked, key=lambda c: -c["mrr_gain"])


def verdict(current: dict, baseline: dict | None, tolerance: float, min_gain: float) -> dict:
    default = default_config(current["report"])
    guard = guardian(current["report"][default].get("all", {}))
    regs = regressions(current, baseline, tolerance) if baseline else []
    cands = candidates(current, min_gain)
    level = CRITICAL if any(f["level"] == "critical" for f in guard) else WARNING if regs or any(f["level"] == "warning" for f in guard) else OK
    return {"default_config": default, "guardian": guard, "regressions": regs, "candidates": cands, "exit_code": level}


def render(current: dict, baseline: dict | None, result: dict, label: str) -> str:
    lines = [f"# Improvement cycle {label}", "",
             f"Corpus: {current.get('corpus', '?')}, {current.get('questions', '?')} questions, measured {current.get('generated', 'unknown date')}. "
             f"Baseline: {baseline.get('generated', 'committed baseline') if baseline else 'none'}.", "",
             "## Verdict", ""]
    names = {0: "healthy", 1: "warning or regression", 2: "CRITICAL"}
    lines.append(f"**{names[result['exit_code']]}** on the default configuration `{result['default_config']}`.")
    lines += ["", "| Metric | Value | Warning below | Critical below | Level |", "|---|---|---|---|---|"]
    for f in result["guardian"]:
        lines.append(f"| {f['metric']} | {f['value']:.3f} | {f['warning_below']} | {f['critical_below']} | {f['level']} |")
    lines += ["", "## Regressions against the baseline", ""]
    lines += [f"- `{r['config']}` {r['metric']}: {r['baseline']:.3f} -> {r['current']:.3f} ({r['delta']:+.3f})" for r in result["regressions"]] or ["None."]
    lines += ["", "## All configurations", "", "| Configuration | Recall@1 | Recall@5 | Recall@10 | MRR | NDCG@10 | held-out MRR |", "|---|---|---|---|---|---|---|"]
    for name, entry in current["report"].items():
        m, h = entry.get("all", {}), entry.get("held_out", {})
        lines.append(f"| {name.replace('|', '/')} | {m.get('recall@1', 0):.3f} | {m.get('recall@5', 0):.3f} | {m.get('recall@10', 0):.3f} | {m.get('mrr', 0):.3f} | {m.get('ndcg@10', 0):.3f} | "
                     f"{h.get('mrr', float('nan')):.3f} |")
    lines += ["", "## Proposed improvements", ""]
    if result["candidates"]:
        for c in result["candidates"][:3]:
            held = "confirmed on the held-out questions" if c["confirmed_on_held_out"] else "NOT confirmed on the held-out questions: do not adopt on this evidence alone"
            lines.append(f"- Switch the default retrieval to `{c['config']}`: MRR {c['mrr_gain']:+.3f}, Recall@10 {c['recall@10']:.3f} ({held}). "
                         "Apply it on a `bob/auto-fix-*` branch, re-run this cycle and the test suite, then review.")
        if len(result["candidates"]) > 3:
            lines.append(f"- {len(result['candidates']) - 3} further candidates are in the JSON report.")
    else:
        lines.append("No other configuration beats the default by the minimum gain without losing Recall@10.")
    lines += ["", "The figures describe this corpus and this machine; they are not a general quality claim.", ""]
    return "\n".join(lines)


def cmd_compare(args) -> int:
    current = load(args.current)
    baseline = load(args.baseline) if args.baseline else None
    result = verdict(current, baseline, args.tolerance, args.min_gain)
    label = args.label or time.strftime("%Y-%m-%d")
    report = render(current, baseline, result, label)
    if args.report_dir:
        out = Path(args.report_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{label}.md").write_text(report, encoding="utf-8")
        (out / f"{label}.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(report)
    return result["exit_code"]


def cmd_run(args) -> int:
    import httpx

    if not re.match(r"^https?://(127\.0\.0\.1|localhost|\[::1\])(:\d+)?$", args.base):
        raise SystemExit("REFUSED: this cycle only runs against a local API")
    http = httpx.Client(base_url=args.base, timeout=httpx.Timeout(300.0, connect=15.0))
    email, password = f"cycle-{uuid.uuid4().hex[:8]}@example.com", f"Cycle-{uuid.uuid4().hex}-Aa1!"
    token = http.post("/auth/register", json={"email": email, "password": password, "full_name": "Cycle", "accept_terms": True}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    org = http.post("/organizations", json={"name": f"Cycle {uuid.uuid4().hex[:6]}"}, headers=headers).json()["id"]
    corpus = json.loads((ROOT / "data" / "processed" / "fastapi_docs.json").read_text(encoding="utf-8"))
    ids = {}
    for page in corpus:
        response = http.post(f"/organizations/{org}/documents", headers=headers, files={"file": (page["path"].replace("/", "__"), page["content"].encode(), "text/markdown")})
        if response.status_code in (200, 201, 202):
            ids[page["path"]] = response.json()["id"]
    print(f"uploaded {len(ids)}/{len(corpus)} pages", flush=True)
    pending, deadline = set(ids.values()), time.time() + args.index_timeout
    while pending and time.time() < deadline:
        listing = http.get(f"/organizations/{org}/documents", headers=headers, params={"limit": 500}).json()
        listing = listing if isinstance(listing, list) else next(v for v in listing.values() if isinstance(v, list))
        pending -= {d["id"] for d in listing if d["status"] in ("completed", "failed")}
        time.sleep(10)
    if pending:
        print(f"{len(pending)} documents were not indexed in time", file=sys.stderr)
        return 3
    measured = subprocess.run([sys.executable, str(ROOT / "scripts" / "measure_retrieval_baseline.py"), "--org", org, "--out", args.run_out, *(["--no-llm"] if args.no_llm else [])], check=False)
    return measured.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="index the corpus on a local stack and measure retrieval")
    run.add_argument("--base", default="http://127.0.0.1:8010")
    run.add_argument("--run-out", default="retrieval_run.json")
    run.add_argument("--index-timeout", type=int, default=3600)
    run.add_argument("--no-llm", action="store_true", help="skip the configurations that need an LLM (HyDE, multi-query, MMR)")
    run.set_defaults(func=cmd_run)
    compare = sub.add_parser("compare", help="compare a measurement with the baseline and write the report")
    compare.add_argument("--current", required=True)
    compare.add_argument("--baseline", default=str(ROOT / "docs" / "project-handover" / "e2e_evidence" / "retrieval_baseline.json"))
    compare.add_argument("--report-dir", default=str(ROOT / "docs" / "operations" / "improvement"))
    compare.add_argument("--label", default="")
    compare.add_argument("--tolerance", type=float, default=0.02)
    compare.add_argument("--min-gain", type=float, default=0.03)
    compare.set_defaults(func=cmd_compare)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

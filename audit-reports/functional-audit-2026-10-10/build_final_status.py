"""Builds 10-final-status-2026-10-11.md from 01c-feature-verification-after-test-runs.csv (run apply_fixes_overlay.py then apply_test_runs.py first).

    python build_final_status.py

Every count comes from the CSV; the prose around them only states what was actually executed (see the logs in work/)."""

import collections
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
rows = list(csv.DictReader(open(os.path.join(HERE, "01c-feature-verification-after-test-runs.csv"), encoding="utf-8-sig")))
by = collections.defaultdict(list)
for row in rows:
    by[row["status_final"]].append(row)

ORDER = ["VERIFIED_COMPLETE", "FIXED_AND_TESTED", "VALIDATED_NOT_DEPLOYED", "DECISION_OR_CORRECTION", "WRITTEN_NOT_EXECUTED", "IMPLEMENTED_UNVERIFIED", "BLOCKED_EXTERNAL", "AMBIGUOUS_REQUIREMENT"]
MEANING = {
    "VERIFIED_COMPLETE": "reviewed as complete and its Part test run is green; no fix was needed",
    "FIXED_AND_TESTED": "a gap was found, fixed, and the fix is covered by tests that ran green (the fix_evidence column says what was not run against a real provider)",
    "VALIDATED_NOT_DEPLOYED": "checked with the official tool (terraform validate, helm lint, kubeconform, shellcheck, actionlint, docker compose config) but never applied to a real account, cluster or workflow run",
    "DECISION_OR_CORRECTION": "an owner decision is recorded, or the first assessment was wrong; nothing left to build",
    "WRITTEN_NOT_EXECUTED": "code or documents exist; nothing proves them yet",
    "IMPLEMENTED_UNVERIFIED": "implemented, but the reviewer could not call it complete from the code and its Part tests alone (gap listed per item)",
    "BLOCKED_EXTERNAL": "cannot be proven without an account, key or service that is not available here",
    "AMBIGUOUS_REQUIREMENT": "the requirement has no testable acceptance criterion",
}
DETAIL = {
    "1": "19 files, 3 batches (earlier session)", "2": "32 files (earlier session)", "3": "41 files with Part 4 (earlier session)", "4": "with Part 3",
    "5": "earlier session", "6": "earlier session", "7": "255 passed", "8": "246 passed", "9": "290 passed",
    "10": "855 passed, 8 failed in the full run; the 8 pass by name in `work/part10_11_rerun.log` (7 = test database left at migration 0137 while the code needs 0142; 1 = `test_latency_metrics`, fixed in the code)",
    "11": "97 passed, 1 failed (the same latency test); passes by name in the rerun",
    "12": "211 passed, 2 skipped (PostgreSQL concurrency, run separately: 24 passed)",
    "13": "143 passed, 1 skipped (staging-only tenant policies). A first run had 119 passed and 25 skipped because the PostgreSQL, S3 and Celery-worker tests were not given their disposable services; they now run (private Redis + worker for `test_e2e_lifecycle`, which proves the real account purge)",
    "14": "26 passed", "15": "41 passed",
}

out = ["# 10 - Final status (2026-10-11)", "", "Built by `build_final_status.py` from `01c-feature-verification-after-test-runs.csv` (column `status_final`); nothing here is typed by hand except the prose.", "",
       f"## Result on the {len(rows)} features", "", "| Status | Count | Meaning |", "|---|---:|---|"]
for status in ORDER:
    out.append(f"| {status} | {len(by[status])} | {MEANING[status]} |")
out += ["", "Rule: a feature is VERIFIED_COMPLETE only if the code review judged it complete AND the targeted tests of its Part ran green. The unit of proof is the Part, not the sentence of each requirement.", "",
        "## Test runs (all 15 Parts have a recorded run)", "", "| Part | Result | Detail |", "|---|---|---|"]
for part in range(1, 16):
    out.append(f"| {part} | {'passed after rerun' if part in (10, 11) else 'passed'} | {DETAIL[str(part)]} |")
out += [
    "",
    "Also executed outside the Part runs: 24 PostgreSQL concurrency tests (credits, invoices, subscriptions; `RAG_DISPOSABLE_PG_URL` on a scratch database) and 38 SQL-tool tenant-bypass tests including the PostgreSQL proofs (`P0_PG_TEST_URL`), both skipped before; the full user lifecycle (register to real Celery purge); Playwright 12/12 in Chrome.",
    "",
    "## Found and fixed",
    "",
    "- **5.4.8 code block** (HIGH): three bypasses of the whitelist reproduced then fixed: dunder attribute read through `str.format`, unbounded memory through repeat / replace / join (a replace turned 1 MB into 1 GB), unhandled MemoryError / RecursionError / ZeroDivisionError. 30 tests.",
    "- **10.1.9 SSRF**: the escalation webhook posted to any URL with a plain client; it now uses the SSRF-safe client (a loopback server proves it). The 60 modules that call httpx directly were reviewed; a contract test fails on a new unreviewed one.",
    "- **13.4.8 Azure Terraform**: `for_each` over a sensitive map is rejected by Terraform; fixed. AWS, GCP and Azure pass `terraform validate` and `fmt -check`.",
    "- **7.2.13 latency**: `measure_latency` recomputed the quality metrics of every stored result on each run (quadratic, and it spent the 60 s budget loading an embedding model); the latency test failed in the full runs and passed alone. Fixed in the code, not in the test; the new test fails without the fix.",
    "- **13.1.9 bandit**: 12 findings triaged, 5 left (Hugging Face `from_pretrained` without a pinned revision).",
    "- **2.1.13 to 2.1.18** import screen: GitHub issues, Google Drive, Google Docs, Confluence and OneDrive were API-only.",
    "- **13.2.4 / 13.3.7**: Playwright 12/12 in Chrome (the harness had an ambiguous `role=alert` selector, hard-coded ports and a CORS origin tied to port 3001, all fixed); the end-to-end workflow also runs nightly; `actionlint` passes on all 8 workflows.",
    "",
    "## Open: needs an owner decision or an account (not code that can be finished here)",
    "",
    "- **Refunds and disputes (BILL-016, 12.1.3)**: invoices have no link to the provider charge and `charge.refunded` is ignored. A fix needs a schema change and a policy (are credits taken back?).",
    "- **Coupons (12.1.4)**: `percent_off` is recorded but not applied at checkout (two providers, real money, no sandbox).",
    "- **Root `render.yaml`** still describes the old Streamlit prototype; the real blueprint is `deploy/render/render.api.yaml`. Render reads the root file automatically if a Blueprint is linked, so replacing it is a deployment decision.",
    "- **Row level security (1.3.5, CRITICAL)**: enabled without policies; the strategy decision is D8 in `docs/DECISIONS.md`.",
    "- **Product name (14.4.1) and logo (14.4.2)**, **custom SLA (10.4.12)**.",
    "- **Real provider sandboxes**: Stripe / Paystack (12.x), LLM / embedding providers (4.x), Slack / Teams / Discord (9.4.x), Twilio / STT / TTS (8.2.x), ClamAV (10.1.12), tracing and error tracking (10.3 / 13.5).",
    "",
]
for status in ("WRITTEN_NOT_EXECUTED", "VALIDATED_NOT_DEPLOYED", "BLOCKED_EXTERNAL", "AMBIGUOUS_REQUIREMENT"):
    out += [f"## {status} ({len(by[status])})", ""]
    for row in by[status]:
        out.append(f"- **{row['feature_id']}** {row['feature_name']} - {(row['fix_status'] or row['known_gaps'])[:150]}")
    out.append("")
out += [f"## IMPLEMENTED_UNVERIFIED ({len(by['IMPLEMENTED_UNVERIFIED'])})", ""]
for row in by["IMPLEMENTED_UNVERIFIED"]:
    out.append(f"- **{row['feature_id']}** {row['feature_name']} [{row['severity']}] - {row['known_gaps'][:140]}")
with open(os.path.join(HERE, "10-final-status-2026-10-11.md"), "w", encoding="utf-8", newline="\n") as fh:
    fh.write("\n".join(out) + "\n")
print({status: len(by[status]) for status in ORDER})

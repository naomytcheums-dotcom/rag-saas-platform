# 08 - Session resume (2026-10-10)

## State
- All 514 features have a first-pass verdict (`verdicts/part01.py` ... `part15.py`), merged by `build_report.py` into `01-feature-verification.csv`. Nothing is NOT_ASSESSED.
- Depth of that first pass: code located, routes/UI wiring checked, existence of tests checked, key files read for the contested items (OAuth UI, verification UI, documents page, chat components, tool budget/fallback wiring, SCIM, toxicity, coupons, escalation, deployment assets). Test bodies were NOT read line by line. Confidence is recorded per item.
- Tests actually executed: see `05-test-execution-log.md`. Only Part 1 has a targeted run. Parts 2-15 are therefore capped at IMPLEMENTED_UNVERIFIED by the build script's test gate (original judgement kept in `assessed_before_test_gate`).

## Files created (reports only; no application code, no tests, no migrations were modified)
`audit-reports/functional-audit-2026-10-10/`: 00-executive-summary.md, 01-feature-verification.csv, 02-part-by-part-report.md, 03-unverified-and-blocked.md, 04-critical-findings.md, 05-test-execution-log.md, 06-remediation-backlog.md, 07-reconciliation.md, 08-resume-session.md, build_report.py, validate_audit.py, probe.py, verdicts/, work/ (source CSV copy, probes, logs).
Outside the folder: nothing. The repository branch was left as found (`bob/auto-fix-20261010-1555`); another session had uncommitted changes (`api/config.py`, `api/security/runtime_guard.py`, `scripts/run_local_preview.py`) that were not touched.

## Not done (explicit)
- No push, no merge, PR #23 untouched, no production access, no external provider call.
- Targeted tests for Parts 2-15 not executed yet (each Part's list is in the verdict files' test_evidence column).
- Test bodies not read; coverage of error cases, permissions and tenant isolation per feature is therefore not proven.
- The 512 figure could not be reproduced (514 unique ids found); see `07-reconciliation.md`.

## How to resume
1. Run the targeted tests for a Part with the safety prefix (unreachable DB URL so nothing can hit production):
   `DATABASE_URL=postgresql+asyncpg://x:x@127.0.0.1:1/none DATABASE_URL_TRANSACTION=<same> REDIS_URL= .venv/Scripts/python.exe -m pytest <files> -q -p no:cacheprovider`
2. Record the result by hand in `work/test_runs.json` as `{"2": {"command": "...", "result": "passed"}}` (use "failed" if any failure, and then downgrade the affected items by editing their verdict).
3. `python build_report.py` then `python validate_audit.py`.
4. Next deepening order: Part 10 (security), Part 12 (billing), Part 1.3.5 (isolation), Part 2 UI gaps, Part 8 unmounted components.

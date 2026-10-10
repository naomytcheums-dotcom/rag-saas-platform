"""Merges work/source_list_514.csv with verdicts/part*.py into 01-feature-verification.csv and the summary reports.
Items without a verdict stay NOT_ASSESSED. Statuses are never inferred from text matches: every verdict is written by hand."""
import csv, glob, importlib.util, os, collections, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
src = list(csv.DictReader(open(os.path.join(HERE, "work", "source_list_514.csv"), encoding="utf-8-sig")))
verdicts = {}
for f in sorted(glob.glob(os.path.join(HERE, "verdicts", "part*.py"))):
    spec = importlib.util.spec_from_file_location(os.path.basename(f)[:-3], f)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    verdicts.update(m.V)

import json
RUNS = json.load(open(os.path.join(HERE, "work", "test_runs.json"), encoding="utf-8")) if os.path.exists(os.path.join(HERE, "work", "test_runs.json")) else {}
# Gate: VERIFIED_COMPLETE needs the Part's targeted tests to have been executed and passed (recorded in work/test_runs.json by hand after a real run).
COLS = ["feature_id", "part", "feature_name", "requirement_description", "declared_status", "verified_status", "assessed_before_test_gate", "tests_executed", "confidence",
        "implementation_evidence", "test_evidence", "security_review", "known_gaps", "external_blockers", "severity",
        "recommended_action", "code_refs_in_source_csv", "test_refs_in_source_csv"]
rows = []
for r in src:
    fid = r["id"]
    v = verdicts.get(fid)
    base = [fid, fid.split(".")[0], r["fonctionnalité"], r["description (texte original)"], r["statut déclaré (CAHIER_DES_CHARGES.md)"]]
    tail = [r["nb fichiers code citant l id"], r["nb tests citant l id"]]
    if v:
        run = RUNS.get(fid.split(".")[0], {})
        gated = v[0]
        if v[0] == "VERIFIED_COMPLETE" and run.get("result") != "passed":
            gated = "IMPLEMENTED_UNVERIFIED"
        executed = (run.get("command", "not executed") + " -> " + run.get("result", "not executed")) if run else "not executed"
        rows.append(base + [gated, v[0], executed, v[1], v[2], v[3], v[4], v[5], v[6], v[7], v[8]] + tail)
    else:
        rows.append(base + ["NOT_ASSESSED", "", "not executed", "", "", "", "", "", "", "", "inspection not yet performed"] + tail)

with open(os.path.join(HERE, "01-feature-verification.csv"), "w", encoding="utf-8-sig", newline="") as fh:
    w = csv.writer(fh); w.writerow(COLS); w.writerows(rows)

by_status = collections.Counter(r[5] for r in rows)
by_part = collections.defaultdict(collections.Counter)
for r in rows: by_part[int(r[1])][r[5]] += 1
assessed = sum(n for s, n in by_status.items() if s != "NOT_ASSESSED")
today = datetime.date.today().isoformat()

with open(os.path.join(HERE, "02-part-by-part-report.md"), "w", encoding="utf-8") as fh:
    fh.write(f"# 02 - Part-by-part report ({today})\n\n| Part | Items | Assessed | " + " | ".join(sorted({s for c in by_part.values() for s in c})) + " |\n")
    statuses = sorted({s for c in by_part.values() for s in c})
    fh.write("|---|---:|---:|" + "---:|" * len(statuses) + "\n")
    for p in sorted(by_part):
        c = by_part[p]; tot = sum(c.values())
        fh.write(f"| {p} | {tot} | {tot - c.get('NOT_ASSESSED', 0)} | " + " | ".join(str(c.get(s, 0)) for s in statuses) + " |\n")
    fh.write("\nPer-item evidence: 01-feature-verification.csv\n")

with open(os.path.join(HERE, "03-unverified-and-blocked.md"), "w", encoding="utf-8") as fh:
    fh.write("# 03 - Unverified, blocked, partial or broken items\n\n")
    for st in ("BLOCKED_EXTERNAL", "IMPLEMENTED_UNVERIFIED", "BROKEN", "PARTIALLY_IMPLEMENTED", "NOT_IMPLEMENTED", "AMBIGUOUS_REQUIREMENT"):
        sel = [r for r in rows if r[5] == st]
        fh.write(f"## {st} ({len(sel)})\n\n")
        for r in sel:
            fh.write(f"- **{r[0]}** {r[2]} - gaps: {r[12] or 'n/a'}; blockers: {r[13] or 'none'}; action: {r[15] or 'n/a'}\n")
        fh.write("\n")
    fh.write(f"## NOT_ASSESSED ({by_status.get('NOT_ASSESSED', 0)})\n\nSee 01-feature-verification.csv (verified_status = NOT_ASSESSED).\n")

with open(os.path.join(HERE, "04-critical-findings.md"), "w", encoding="utf-8") as fh:
    fh.write("# 04 - Critical and high findings\n\n")
    for r in rows:
        if r[14] in ("CRITICAL", "HIGH"):
            fh.write(f"## {r[0]} {r[2]} - {r[14]}\n- status: {r[5]} (code assessment before test gate: {r[6]}; confidence {r[8]})\n- evidence: {r[9]}\n- gap: {r[12]}\n- security: {r[11]}\n- external blockers: {r[13] or 'none'}\n- action: {r[15]}\n\n")

with open(os.path.join(HERE, "06-remediation-backlog.md"), "w", encoding="utf-8") as fh:
    fh.write("# 06 - Remediation backlog (ordered by severity)\n\n")
    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4, "": 5}
    n = 0
    for r in sorted([x for x in rows if x[15] and x[15] not in ("none", "inspection not yet performed")], key=lambda x: (order.get(x[14], 5), x[0])):
        n += 1
        fh.write(f"- REM-{n:03d} [{r[14]}] feature {r[0]} ({r[2]}): {r[15]}\n")

with open(os.path.join(HERE, "00-executive-summary.md"), "w", encoding="utf-8") as fh:
    fh.write(f"# 00 - Executive summary ({today})\n\n")
    fh.write(f"- Features in the source list: {len(rows)} (unique ids: {len({r[0] for r in rows})}). See 07-reconciliation.md for 514 vs 512.\n")
    fh.write(f"- Individually assessed so far: {assessed}; NOT_ASSESSED: {by_status.get('NOT_ASSESSED', 0)}.\n\n")
    fh.write("| Verified status | Count |\n|---|---:|\n")
    for s, n in sorted(by_status.items()): fh.write(f"| {s} | {n} |\n")
    gated = sum(1 for r in rows if r[6] == "VERIFIED_COMPLETE" and r[5] != "VERIFIED_COMPLETE")
    fh.write(f"\n**How to read VERIFIED_COMPLETE:** {gated} items were judged complete after reading the code and checking the wiring and the existence of tests, but were held back to IMPLEMENTED_UNVERIFIED because the Part's targeted tests were not executed in this audit (column `assessed_before_test_gate` keeps the original judgement). Test bodies were not read line by line; confidence levels say so.\n")
    fh.write("\n## Readiness: NO-GO for commercial launch (as of this audit)\n\n")
    fh.write("Reasons, each backed by 04-critical-findings.md, 03-unverified-and-blocked.md or the 2026-10-10 radiography:\n")
    fh.write("1. Tenant isolation has no database barrier (1.3.5, audit R-01).\n2. Background jobs (permanent account deletion 1.1.10, scheduled reindex, sync, billing renewals, evaluation jobs) depend on a Celery worker/beat that the production image does not run (audit R-02).\n")
    fh.write("3. Billing has never been run against a provider sandbox, and coupons (12.1.4), Flutterwave and voice-minute limits (12.3.6) are absent.\n4. Eval Lab and quality detectors have never produced a real baseline; no held-out split exists (7.1.7).\n")
    fh.write("5. Product surface gaps: no email-verification screen (1.1.4), no OAuth buttons (1.1.5/1.1.6), minimal documents page (2.2.x), many chat/voice components exist but are not mounted (8.1.x, 8.2.x), no human-escalation API or dashboard (15.1.x).\n")
    fh.write("6. Absent items: SCIM (10.4.3), toxicity filter (10.2.7), per-organization retention (10.4.6), dedicated tenant/database (10.4.7/10.4.8), analytics gap reports (11.2.7/9/10/14/15/16), deployment targets other than Render/Docker (13.4.x), PDFs and demo video (14.2.x).\n")
    fh.write("\nStrengths with direct evidence: auth/2FA/sessions, organization roles and invitations, document ingestion for the common formats, chunking strategies wired into ingestion, hybrid retrieval, litellm provider abstraction, citations and quality services wired into generation, public API and SDK packages, billing state machine and invoice rules with extensive tests.\n")
    fh.write("\nLimits: read-only audit of the repository; no production, no external provider; tests run on SQLite with services disabled (see 05-test-execution-log.md).\n")
print("rows", len(rows), "assessed", assessed, dict(by_status))

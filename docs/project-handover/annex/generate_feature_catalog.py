"""Build 12_COMPLETE_FEATURE_CATALOG.md from the audit CSV (read-only; nothing is typed by hand except the part titles and the status legend)."""

import csv
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "audit-reports" / "functional-audit-2026-10-10" / "01c-feature-verification-after-test-runs.csv"
OUT = ROOT / "docs" / "project-handover" / "12_COMPLETE_FEATURE_CATALOG.md"
TITLES = {
    "1": "Structure and multi-tenancy (accounts, organizations, roles, quotas, white-label basics)",
    "2": "Universal knowledge base (document import, extraction, metadata, batch jobs)",
    "3": "Advanced RAG pipeline (extraction, chunking, embeddings, retrieval, advanced retrieval)",
    "4": "Multi-LLM and embeddings (providers, routing, configuration)",
    "5": "AI agents (orchestrator, tools, agent configuration, workflows)",
    "6": "Citations and anti-hallucination",
    "7": "Evaluation Lab (datasets, metrics, regression, comparison)",
    "8": "User interface (chat, streaming, voice, rendering)",
    "9": "Public API and integrations (REST, SDKs, widget, chat platforms, webhooks)",
    "10": "Security and governance (auth hardening, guardrails, compliance, SSO)",
    "11": "Admin dashboard and analytics",
    "12": "Billing and monetization",
    "13": "Developer experience (quality tooling, tests, CI/CD, deployment, observability)",
    "14": "Documentation and deliverables (architecture docs, product, brand)",
    "15": "Human in the loop (escalation, approval, feedback loop)",
}
LEGEND = [
    ("VERIFIED_COMPLETE", "reviewed as complete AND the targeted tests of its Part ran green; no fix was needed"),
    ("FIXED_AND_TESTED", "a gap was found, fixed, and the fix is covered by tests that ran green (not necessarily against a real provider)"),
    ("DECISION_OR_CORRECTION", "an owner decision is recorded in docs/DECISIONS.md, or the first assessment was wrong; nothing left to build"),
    ("VALIDATED_NOT_DEPLOYED", "checked with the official tool (terraform validate, helm lint, kubeconform, shellcheck, actionlint, compose config) but never applied to a real account or cluster"),
    ("IMPLEMENTED_UNVERIFIED", "implemented, but the reviewer could not call it complete from the code and its Part tests alone"),
    ("WRITTEN_NOT_EXECUTED", "code or documents exist; nothing proves them yet"),
    ("BLOCKED_EXTERNAL", "cannot be proven without an account, key or service that is not available in the development environment"),
    ("AMBIGUOUS_REQUIREMENT", "the requirement has no testable acceptance criterion"),
]


def clean(value: str, limit: int = 420) -> str:
    value = " ".join((value or "").split()).replace("|", "/")
    return value if len(value) <= limit else value[: limit - 1] + "…"


def main() -> None:
    rows = list(csv.DictReader(open(SRC, encoding="utf-8-sig")))
    by_part = defaultdict(list)
    for r in rows:
        by_part[r["part"]].append(r)
    totals = Counter(r["status_final"] for r in rows)
    lines = [
        "# 12 - Complete feature catalog (514 features)", "",
        f"Generated from `{SRC.relative_to(ROOT).as_posix()}` by `docs/project-handover/annex/generate_feature_catalog.py` (column `status_final`). "
        "Each entry gives the requirement (as written in the cahier des charges, French), the evidence found in the code, the tests, the known gaps and the next action.", "",
        "## How to read the statuses", "", "| Status | Meaning |", "|---|---|",
    ]
    lines += [f"| `{k}` | {v} |" for k, v in LEGEND]
    lines += ["", "A feature is `VERIFIED_COMPLETE` only if the code review judged it complete AND the tests of its Part ran green. The unit of proof is the Part, not each sentence of each requirement. "
              "`FIXED_AND_TESTED` is not 'deployed': nothing in this catalog proves a feature works in production unless it says so.", "", "## Totals", "", "| Status | Count |", "|---|---:|"]
    lines += [f"| {k} | {totals.get(k, 0)} |" for k, _ in LEGEND]
    ready = totals["VERIFIED_COMPLETE"] + totals["FIXED_AND_TESTED"] + totals["DECISION_OR_CORRECTION"]
    unproven = totals["VALIDATED_NOT_DEPLOYED"] + totals["IMPLEMENTED_UNVERIFIED"] + totals["WRITTEN_NOT_EXECUTED"] + totals["BLOCKED_EXTERNAL"] + totals["AMBIGUOUS_REQUIREMENT"]
    lines += [f"| **Total** | **{len(rows)}** |", "",
              f"Two notions of 'ready' were used in earlier summaries and are defined here once: **proven in tests** = VERIFIED_COMPLETE + FIXED_AND_TESTED = {totals['VERIFIED_COMPLETE'] + totals['FIXED_AND_TESTED']}; "
              f"**closed** = proven in tests + DECISION_OR_CORRECTION = {ready} ({100 * ready / len(rows):.0f} %); **not yet proven** = the other four statuses = {unproven}. "
              "The cahier des charges text says 515 features (Part 15 was truncated in the original message); this catalog has 514 rows.", ""]
    for part in sorted(by_part, key=int):
        items = by_part[part]
        c = Counter(r["status_final"] for r in items)
        lines += [f"## Part {part} - {TITLES.get(part, '')}", "", f"{len(items)} features: " + ", ".join(f"{k} {v}" for k, v in c.most_common()), ""]
        for r in items:
            lines += [
                f"### {r['feature_id']} - {clean(r['feature_name'], 120)}  `{r['status_final']}`",
                f"- **Requirement:** {clean(r['requirement_description'])}",
                f"- **Implementation:** {clean(r['implementation_evidence'])}",
                f"- **Tests:** {clean(r['test_evidence'])} (Part run: {r['test_run_result'] or 'n/a'})",
                f"- **Known gaps:** {clean(r['known_gaps'])}" + (f" | **External blockers:** {clean(r['external_blockers'])}" if r["external_blockers"] not in ("", "none") else ""),
                f"- **Severity / next action:** {r['severity'] or 'n/a'} / {clean(r['recommended_action'])}"
                + (f" | **Fix:** {clean(r['fix_evidence'])}" if r["fix_evidence"] else ""), "",
            ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("wrote", OUT, len(rows), "rows", len(lines), "lines")


main()

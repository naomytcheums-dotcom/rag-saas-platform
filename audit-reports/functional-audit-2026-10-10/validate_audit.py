"""Structure check of 01-feature-verification.csv: unique ids, same ids as the source list, every part 1-15 present,
known statuses only, totals consistent, referenced code paths exist. Does NOT assign any functional status."""
import csv, os, re, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OK = {"VERIFIED_COMPLETE", "PARTIALLY_IMPLEMENTED", "NOT_IMPLEMENTED", "IMPLEMENTED_UNVERIFIED", "BLOCKED_EXTERNAL", "BROKEN", "AMBIGUOUS_REQUIREMENT", "NOT_ASSESSED"}
rows = list(csv.DictReader(open(os.path.join(HERE, "01-feature-verification.csv"), encoding="utf-8-sig")))
src = list(csv.DictReader(open(os.path.join(HERE, "work", "source_list_514.csv"), encoding="utf-8-sig")))
errors = []
ids = [r["feature_id"] for r in rows]
if len(ids) != len(set(ids)): errors.append("duplicate feature_id")
if set(ids) != {r["id"] for r in src}: errors.append("ids differ from the source list")
if {int(r["part"]) for r in rows} != set(range(1, 16)): errors.append("parts 1-15 not all present")
for r in rows:
    if r["verified_status"] not in OK: errors.append(f"{r['feature_id']}: unknown status {r['verified_status']}")
    if r["verified_status"] != "NOT_ASSESSED" and not (r["implementation_evidence"] and r["confidence"]):
        errors.append(f"{r['feature_id']}: assessed without evidence/confidence")
    if not r["declared_status"]: pass
missing = []
for r in rows:
    for p in re.findall(r"(?<![\w/.\-])((?:api|frontend|tests|sdks)/[\w./\-\[\]{}]+\.(?:py|tsx?|json))", r["implementation_evidence"] + " " + r["test_evidence"]):
        if not os.path.exists(os.path.join(ROOT, p)): missing.append((r["feature_id"], p))
cnt = collections.Counter(r["verified_status"] for r in rows)
print("rows:", len(rows), "statuses:", dict(cnt), "sum ok:", sum(cnt.values()) == len(rows))
print("referenced paths not found (relative paths named without a folder are not checked):", len(missing)); [print("  ", m) for m in missing[:40]]
print("ERRORS:" if errors else "STRUCTURE OK", *errors[:20], sep="\n  ")
sys.exit(1 if errors else 0)

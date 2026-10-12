"""Tenant reachability of every table (TEN-006, phase 5 of the 2026-10-12 security audit). Reads the SQLAlchemy metadata only: no database, no network.

For each table: DIRECT (has an organization_id column), ORG_ROOT (organizations), USER_SCOPED (no organization but a foreign key to users),
INDIRECT (a chain of foreign keys leads to a DIRECT table: the shortest chain is listed), or GLOBAL (no chain at all: system or catalogue data).
A GLOBAL table must never hold one organization's data; the list is the review checklist, and tests/test_tenant_table_classification.py pins it.

    RAG_ENV_FILE=.no-env DATABASE_URL=sqlite:///:memory: python audit-reports/phase5-2026-10-12/tenant_reachability.py
"""

import collections
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def classify(metadata) -> dict[str, tuple[str, str]]:
    tables = metadata.tables
    direct = {name for name, table in tables.items() if "organization_id" in table.c}
    parents = collections.defaultdict(list)  # child table -> parent tables
    for name, table in tables.items():
        for fk in table.foreign_keys:
            parents[name].append(fk.column.table.name)
    result: dict[str, tuple[str, str]] = {}
    for name, table in sorted(tables.items()):
        if name == "organizations":
            result[name] = ("ORG_ROOT", "")
        elif name in direct:
            result[name] = ("DIRECT", "")
        else:
            path, seen, queue = None, {name}, collections.deque([(name, [name])])
            while queue and path is None:
                current, trail = queue.popleft()
                for parent in parents.get(current, []):
                    if parent in direct or parent == "organizations":
                        path = trail + [parent]
                        break
                    if parent not in seen:
                        seen.add(parent)
                        queue.append((parent, trail + [parent]))
            if path:
                result[name] = ("INDIRECT", " -> ".join(path))
            elif "users" in parents.get(name, []):
                result[name] = ("USER_SCOPED", "users")
            else:
                result[name] = ("GLOBAL", "")
    return result


def main() -> int:
    import api.models  # noqa: F401 -- registers every model
    from api.database import Base

    result = classify(Base.metadata)
    out = Path(__file__).with_name("tenant_table_classification.csv")
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["table", "class", "path_to_an_organization"])
        for name, (kind, path) in result.items():
            writer.writerow([name, kind, path])
    counts = collections.Counter(kind for kind, _ in result.values())
    print(f"{len(result)} tables:", dict(counts))
    print("GLOBAL:", sorted(n for n, (k, _) in result.items() if k == "GLOBAL"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

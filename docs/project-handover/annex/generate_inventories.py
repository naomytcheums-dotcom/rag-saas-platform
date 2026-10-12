"""Regenerate the machine-made annexes of docs/project-handover/ from the code (read-only: imports the app, never connects to a database).

    RAG_ENV_FILE=.no-env JWT_SECRET_KEY=x SESSION_MIDDLEWARE_SECRET=x SUPPORT_EMAIL=a@b.test AUDIT_LOG_HMAC_SECRET_KEY=x \
    DATABASE_URL=postgresql+asyncpg://u:p@localhost:1/none python docs/project-handover/annex/generate_inventories.py
"""

import ast
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def first_doc_line(path: Path) -> str:
    try:
        doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8")))
    except Exception:
        return ""
    return (doc or "").strip().splitlines()[0][:200] if doc else ""


def routes() -> None:
    from api.main import app

    spec = app.openapi()
    rows = []
    for path, ops in sorted(spec["paths"].items()):
        for method, op in ops.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            tags = ",".join(op.get("tags", []))
            secured = "yes" if op.get("security") else "no/unknown"
            rows.append([method.upper(), path, tags, op.get("operationId", ""), (op.get("summary") or "")[:100], secured])
    with open(OUT / "api_routes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["method", "path", "tag", "operation_id", "summary", "declares_security"])
        w.writerows(rows)
    by_tag = Counter(r[2].split(",")[0] or "(untagged)" for r in rows)
    (OUT / "api_routes_by_tag.json").write_text(json.dumps(by_tag.most_common(), indent=1), encoding="utf-8")
    print("routes", len(rows), "tags", len(by_tag))


def models() -> None:
    import api.models  # noqa: F401
    from api.models import Base

    lines = ["# Database tables (generated from SQLAlchemy metadata)", "", f"{len(Base.metadata.tables)} tables.", ""]
    rows = []
    for name, t in sorted(Base.metadata.tables.items()):
        fks = sorted({f"{fk.parent.name}->{fk.column.table.name}.{fk.column.name}" for fk in t.foreign_keys})
        rows.append([name, len(t.columns), "yes" if "organization_id" in t.columns else "no", ";".join(fks), ";".join(sorted(i.name or "" for i in t.indexes))])
        lines += [f"## {name}", f"- columns ({len(t.columns)}): " + ", ".join(f"{c.name}:{str(c.type)[:24]}{'*' if c.primary_key else ''}" for c in t.columns), f"- foreign keys: {', '.join(fks) or 'none'}", f"- indexes: {', '.join(sorted(i.name or '?' for i in t.indexes)) or 'none'}", ""]
    (OUT / "database_tables.md").write_text("\n".join(lines), encoding="utf-8")
    with open(OUT / "database_tables.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["table", "columns", "has_organization_id", "foreign_keys", "indexes"])
        w.writerows(rows)
    print("tables", len(rows), "with organization_id", sum(1 for r in rows if r[2] == "yes"))


def migrations() -> None:
    rows = []
    for p in sorted((ROOT / "api" / "alembic" / "versions").glob("*.py")):
        text = p.read_text(encoding="utf-8")
        rev = re.search(r'^revision\s*(?::\s*str)?\s*=\s*["\']([^"\']+)', text, re.M)
        down = re.search(r'^down_revision\s*(?::[^=]+)?=\s*(.+)$', text, re.M)
        doc = first_doc_line(p)
        rows.append([p.name, rev.group(1) if rev else "", down.group(1).strip() if down else "", doc])
    with open(OUT / "migrations.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file", "revision", "down_revision", "docstring"])
        w.writerows(rows)
    print("migrations", len(rows))


def frontend() -> None:
    base = ROOT / "frontend" / "app"
    rows = []
    for p in sorted(base.rglob("page.tsx")):
        route = "/" + "/".join(p.relative_to(base).parts[:-1])
        text = p.read_text(encoding="utf-8")
        apis = sorted(set(re.findall(r'api\.(?:get|post|put|patch|delete|postFile|postMultipart|putMultipart|fetchRaw)\s*(?:<[^>]*>)?\(\s*[`"\']([^`"\']+)', text)))
        rows.append([route or "/", str(p.relative_to(ROOT)), len(text.splitlines()), ";".join(apis)[:600]])
    with open(OUT / "frontend_pages.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["route", "file", "lines", "api_paths_called_directly"])
        w.writerows(rows)
    print("pages", len(rows))


def modules() -> None:
    lines = ["# Python modules (generated: first line of each module docstring)", ""]
    for folder in ("routers", "services", "tasks", "tools", "security", "models", "agents", "middleware", "mcp", "workflows"):
        d = ROOT / "api" / folder
        if not d.exists():
            continue
        files = sorted(d.rglob("*.py"))
        lines += [f"## api/{folder}/ ({len(files)} files)", ""]
        for p in files:
            if p.name == "__init__.py":
                continue
            lines.append(f"- `{p.relative_to(ROOT).as_posix()}` ({len(p.read_text(encoding='utf-8').splitlines())} lines): {first_doc_line(p)}")
        lines.append("")
    (OUT / "python_modules.md").write_text("\n".join(lines), encoding="utf-8")
    print("modules written")


def tests() -> None:
    counts = defaultdict(int)
    for p in (ROOT / "tests").rglob("test_*.py"):
        text = p.read_text(encoding="utf-8")
        counts[str(p.relative_to(ROOT).as_posix())] = len(re.findall(r"^\s*(?:async )?def test_", text, re.M))
    with open(OUT / "tests_inventory.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file", "test_functions"])
        w.writerows(sorted(counts.items()))
    print("test files", len(counts), "test functions", sum(counts.values()))


if __name__ == "__main__":
    for step in (routes, models, migrations, frontend, modules, tests):
        try:
            step()
        except Exception as exc:  # keep going: a failed annex is reported, not hidden
            print("FAILED", step.__name__, type(exc).__name__, str(exc)[:200])

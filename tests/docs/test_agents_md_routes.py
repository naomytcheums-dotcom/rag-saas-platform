"""agents.md documents the Eval Lab and MCP endpoints; they must exist (Lot I). The previous text named `/api/eval/*` and `/mcp/v1/servers…`,
which never existed in the 943 operations of the API (found by the 2026-10-10 audit)."""

import re
from pathlib import Path

from api.main import app

AGENTS = (Path(__file__).resolve().parent.parent.parent / "agents.md").read_text(encoding="utf-8")


def _normalize(path: str) -> str:
    return re.sub(r"\{[^}]*\}", "{}", path.rstrip("/"))


def _documented_endpoints() -> set[str]:
    start = AGENTS.index("### 1.4 Eval Lab")
    end = AGENTS.index("## 2. OPERATIONAL MODES")
    found = set()
    for line in AGENTS[start:end].splitlines():
        if line.startswith("- "):
            found |= {m.rstrip(".,;)") for m in re.findall(r"(?<![\w{])(/[A-Za-z0-9_\-/{}]+)", line)}
    return {_normalize(p) for p in found if len(p) > 3}


def test_every_endpoint_documented_in_agents_md_exists():
    live = {_normalize(path) for path in app.openapi()["paths"]}
    documented = _documented_endpoints()
    assert len(documented) >= 12, documented  # the parser must really find the lists
    missing = sorted(p for p in documented if p not in live and not any(item.endswith(p) for item in live))
    assert missing == [], f"documented in agents.md but absent from the API: {missing}"


def test_the_removed_phantom_routes_are_not_documented_again():
    assert "/api/eval/" not in AGENTS.replace("il n'existe PAS de dossier `api/eval/` ni de chemin `/api/eval/*`", "")
    assert "/mcp/v1/servers" not in AGENTS

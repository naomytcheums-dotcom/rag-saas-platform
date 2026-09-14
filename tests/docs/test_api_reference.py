"""Validates docs/api/ against the real FastAPI app rather than trusting
hand-written endpoint tables: every path documented in docs/api/*.md
must actually exist in the live OpenAPI schema, and the committed
docs/api/openapi.json export must match what the running app reports
right now (not a stale snapshot from an earlier refactor).
"""
import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Matches lines like "POST /organizations/{org_id}/documents" inside
# fenced code blocks in the api docs.
METHOD_PATH_RE = re.compile(
    r"^\s*(GET|POST|PATCH|PUT|DELETE)\s+(/[^\s`]+)\s*$", re.MULTILINE
)


def _load_live_schema():
    import sys

    sys.path.insert(0, str(REPO_ROOT))
    from api.main import app  # noqa: E402

    return app.openapi()


def _load_committed_schema():
    path = REPO_ROOT / "docs" / "api" / "openapi.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _path_matches(documented: str, real_paths) -> bool:
    """A documented path with placeholder segments (e.g. {document_id})
    matches a real OpenAPI path with the same shape, regardless of the
    exact placeholder name (docs may use a friendlier name than the
    code's own parameter name).
    """
    doc_pattern = re.sub(r"\{[^}]+\}", r"\\{[^}]+\\}", re.escape(documented).replace(r"\{", "{").replace(r"\}", "}"))
    doc_pattern = re.sub(r"\\\{[^}]+\\\}", r"\\{[^}]+\\}", re.escape(documented))
    segments = documented.split("/")
    for real in real_paths:
        real_segments = real.split("/")
        if len(real_segments) != len(segments):
            continue
        if all(
            (d.startswith("{") and d.endswith("}") and r.startswith("{") and r.endswith("}"))
            or d == r
            for d, r in zip(segments, real_segments)
        ):
            return True
    return False


def test_committed_openapi_export_matches_live_app():
    live = _load_live_schema()
    committed = _load_committed_schema()
    assert set(live["paths"].keys()) == set(committed["paths"].keys()), (
        "docs/api/openapi.json is stale — regenerate it from api.main.app.openapi() "
        "after any router change (see docs/developer/API.md)."
    )


@pytest.mark.parametrize(
    "doc_file",
    sorted((REPO_ROOT / "docs" / "api").glob("*.md")),
    ids=lambda p: p.name,
)
def test_documented_endpoints_exist_in_live_schema(doc_file: Path):
    live = _load_live_schema()
    real_paths = list(live["paths"].keys())

    text = doc_file.read_text(encoding="utf-8")
    missing = []
    for method, raw_path in METHOD_PATH_RE.findall(text):
        path = raw_path.split("?", 1)[0]
        # Documented example paths sometimes use a friendlier alias
        # (e.g. /documents/{document_id}/export/{markdown|json|pdf|docx})
        # — normalize simple pipe-alternatives to a single placeholder
        # segment before matching.
        normalized = re.sub(r"\{[a-zA-Z_|]+\}", "{param}", path)
        if not _path_matches(normalized, [re.sub(r"\{[a-zA-Z_]+\}", "{param}", p) for p in real_paths]):
            missing.append(f"{method} {path}")

    assert not missing, f"{doc_file.name} documents endpoint(s) not found in the live API: {missing}"

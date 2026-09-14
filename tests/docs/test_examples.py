"""Sanity-check code examples embedded in the docs: syntax validity for
Python/JSON snippets, and that referenced SDK symbols actually exist in
the real SDK source rather than a name that was renamed or removed.
"""
import ast
import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

FENCE_RE = re.compile(r"```(\w+)\n(.*?)```", re.DOTALL)


def _code_blocks(md_path: Path, lang: str):
    text = md_path.read_text(encoding="utf-8")
    for match in FENCE_RE.finditer(text):
        if match.group(1) == lang:
            yield match.group(2)


PYTHON_DOC_FILES = [
    REPO_ROOT / "docs" / "developer" / "SDK_PYTHON.md",
    REPO_ROOT / "docs" / "tutorials" / "UPLOAD_AND_QUERY_DOCUMENTS.md",
    REPO_ROOT / "docs" / "tutorials" / "FINE_TUNE_A_MODEL.md",
]


@pytest.mark.parametrize("md_file", PYTHON_DOC_FILES, ids=lambda p: p.name)
def test_python_examples_parse(md_file: Path):
    if not md_file.exists():
        pytest.skip(f"{md_file} not found")
    blocks = list(_code_blocks(md_file, "python"))
    for block in blocks:
        try:
            ast.parse(block)
        except SyntaxError as exc:
            pytest.fail(f"Invalid Python example in {md_file}: {exc}\n{block}")


def test_json_examples_in_api_docs_parse():
    api_docs_dir = REPO_ROOT / "docs" / "api"
    json_blocks_checked = 0
    for md_file in api_docs_dir.glob("*.md"):
        text = md_file.read_text(encoding="utf-8")
        for match in FENCE_RE.finditer(text):
            if match.group(1) != "json":
                continue
            snippet = match.group(2).strip()
            if not snippet:
                continue
            try:
                json.loads(snippet)
            except json.JSONDecodeError as exc:
                pytest.fail(f"Invalid JSON example in {md_file}: {exc}\n{snippet}")
            json_blocks_checked += 1
    assert json_blocks_checked > 0, "Expected at least one JSON example under docs/api/"


def test_python_sdk_client_class_exists():
    sdk_init = REPO_ROOT / "sdks" / "python"
    assert sdk_init.exists(), "sdks/python is documented but missing on disk"
    source_files = list(sdk_init.rglob("*.py"))
    assert any(
        "RagSaasClient" in f.read_text(encoding="utf-8") for f in source_files
    ), "docs/developer/SDK_PYTHON.md references RagSaasClient, but it wasn't found in sdks/python"


def test_js_sdk_client_class_exists():
    sdk_dir = REPO_ROOT / "sdks" / "js"
    assert sdk_dir.exists(), "sdks/js is documented but missing on disk"
    source_files = list(sdk_dir.rglob("*.ts")) + list(sdk_dir.rglob("*.js"))
    assert any(
        "RagSaasClient" in f.read_text(encoding="utf-8") for f in source_files
    ), "docs/developer/SDK_JS.md references RagSaasClient, but it wasn't found in sdks/js"

"""Every relative markdown link inside docs/ and the root *.md files must
resolve to a real file on disk. Catches broken links from renames/moves
without requiring a human to click every link by hand.
"""
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def _iter_markdown_files():
    for path in REPO_ROOT.glob("*.md"):
        yield path
    for path in (REPO_ROOT / "docs").rglob("*.md"):
        yield path
    for path in (REPO_ROOT / "sdks").glob("*/README.md"):
        yield path
    readme = REPO_ROOT / "src" / "README.md"
    if readme.exists():
        yield readme


def _is_external_or_special(link: str) -> bool:
    if link.startswith(("http://", "https://", "mailto:")):
        return True
    if link.startswith("#"):
        return True
    # Literal placeholder syntax used in prose to show the Markdown link
    # form itself (e.g. "`[label](url)`"), not a real link.
    if link in ("url", "..."):
        return True
    return False


def _strip_code_spans_and_fences(text: str) -> str:
    """Remove fenced code blocks and inline code spans so link-like text
    used as a literal example (e.g. "`[label](url)`" inside docs about
    Markdown syntax) is never mistaken for a real link.
    """
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"`[^`\n]+`", "", text)
    return text


def _strip_anchor(link: str) -> str:
    return link.split("#", 1)[0]


MARKDOWN_FILES = list(_iter_markdown_files())


@pytest.mark.parametrize("md_file", MARKDOWN_FILES, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_relative_links_resolve(md_file: Path):
    text = _strip_code_spans_and_fences(md_file.read_text(encoding="utf-8"))
    broken = []
    for match in MD_LINK_RE.finditer(text):
        link = match.group(1).strip()
        if not link or _is_external_or_special(link):
            continue
        target = _strip_anchor(link)
        if not target:
            continue
        resolved = (md_file.parent / target).resolve()
        if not resolved.exists():
            broken.append(link)
    assert not broken, f"Broken relative link(s) in {md_file}: {broken}"


def test_sidebar_entries_resolve():
    sidebar = REPO_ROOT / "docs" / "_sidebar.md"
    text = sidebar.read_text(encoding="utf-8")
    broken = []
    for match in MD_LINK_RE.finditer(text):
        link = match.group(1).strip()
        if _is_external_or_special(link):
            continue
        target = _strip_anchor(link)
        resolved = (sidebar.parent / target).resolve()
        if not resolved.exists():
            broken.append(link)
    assert not broken, f"Broken _sidebar.md link(s): {broken}"

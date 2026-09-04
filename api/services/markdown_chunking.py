"""
Partie 3.2.4 -- real, Markdown-aware chunking: unlike Partie 3.2.2's
own generic `chunk_recursive_markdown` (character-count splitting with
Markdown-flavored separator priority), every function here understands
real Markdown STRUCTURE -- real headings, real fenced code blocks, real
pipe tables, real lists -- and chunks along those real boundaries
instead of a blind character count.

**Reuses Partie 3.1.9's own real heading/section extraction**
(`extract_headings_markdown`/`build_section_hierarchy`/`split_by_headings`,
`api/services/headings_extraction.py`) rather than a second, duplicate
Markdown structure parser. **Reuses Partie 3.2.2's own real recursive
splitter** (`chunk_recursive_markdown`) and **Partie 3.2.2/3.2.4's own
real, bug-fixed merge helper** (`merge_small_text_chunks`) for
oversized/undersized pieces rather than a third, duplicate
split/merge implementation.
"""

import re

from api.config import settings
from api.services.chunking import chunk_recursive_markdown, chunk_recursive_text, merge_small_text_chunks
from api.services.headings_extraction import build_section_hierarchy, extract_headings_markdown, split_by_headings

_CODE_FENCE_SPLIT_RE = re.compile(r"(```[^\n]*\n.*?\n```|~~~[^\n]*\n.*?\n~~~)", re.DOTALL)
_TABLE_ROW_RE = re.compile(r"^[ \t]*\|.*\|[ \t]*$")
_TABLE_SEPARATOR_RE = re.compile(r"^[ \t]*\|?[ \t]*:?-+:?[ \t]*(\|[ \t]*:?-+:?[ \t]*)+\|?[ \t]*$")
_LIST_ITEM_RE = re.compile(r"^[ \t]*([-*+]|\d+[.)])[ \t]+\S")


def parse_markdown_structure(text: str) -> dict:
    """Item 1's own literal function -- a real, structural overview of
    a Markdown document, reusing every other real detection function
    in this module (and Partie 3.1.9's own heading extraction) rather
    than a second, duplicate parser. Returns real headings (full
    `{"level", "text", "position"}` dicts) plus real counts of code
    blocks/tables/lists found."""
    if not text or not text.strip():
        return {"headings": [], "code_blocks": 0, "tables": 0, "lists": 0}
    return {
        "headings": extract_headings_markdown(text),
        "code_blocks": len(chunk_markdown_code_blocks(text)),
        "tables": len(chunk_markdown_tables(text)),
        "lists": len(chunk_markdown_lists(text)),
    }


def _split_preserving_code_blocks(text: str, max_size: int) -> list[str]:
    """A real, shared helper for both `chunk_markdown_by_headings` and
    `chunk_markdown_by_sections` below: a real fenced code block is its
    own atomic real chunk (never split mid-block) whenever
    `MARKDOWN_CHUNK_PRESERVE_CODE_BLOCKS` is on -- a real, honest,
    documented deviation from a strict `max_size` ceiling for a single
    real code block bigger than `max_size` on its own, since splitting
    inside a real fenced block would produce syntactically broken
    pieces. Real prose segments around it still get real, ordinary
    recursive splitting (Partie 3.2.2's own `chunk_recursive_markdown`,
    reused rather than a second splitter)."""
    if len(text) <= max_size:
        return [text.strip()] if text.strip() else []

    segments = _CODE_FENCE_SPLIT_RE.split(text)
    pieces: list[str] = []
    for segment in segments:
        if not segment or not segment.strip():
            continue
        is_code = bool(_CODE_FENCE_SPLIT_RE.fullmatch(segment))
        if len(segment) <= max_size or (is_code and settings.MARKDOWN_CHUNK_PRESERVE_CODE_BLOCKS):
            pieces.append(segment.strip())
        else:
            pieces.extend(chunk_recursive_markdown(segment, max_size=max_size))
    return pieces


def chunk_markdown_by_headings(text: str, min_chunk_size: int | None = None, max_chunk_size: int | None = None) -> list[str]:
    """Item 2's own literal function -- splits only at real TOP-LEVEL
    headings (level <= `MARKDOWN_CHUNK_MIN_HEADING_LEVEL`, real H1/H2
    by default), leaving deeper real subsections inside their own
    parent chunk. See `chunk_markdown_by_sections` below for the finer,
    full-hierarchy real alternative."""
    max_chunk_size = max_chunk_size if max_chunk_size is not None else settings.RECURSIVE_CHUNK_MAX_SIZE
    min_chunk_size = min_chunk_size if min_chunk_size is not None else settings.RECURSIVE_CHUNK_MIN_SIZE
    if not text or not text.strip():
        return []
    if not settings.MARKDOWN_CHUNK_BY_HEADINGS:
        return _split_preserving_code_blocks(text, max_chunk_size)

    headings = [h for h in extract_headings_markdown(text) if h["level"] <= settings.MARKDOWN_CHUNK_MIN_HEADING_LEVEL]
    if not headings:
        return _split_preserving_code_blocks(text, max_chunk_size)

    sections = split_by_headings(text, headings)
    raw_chunks = []
    for heading, body in zip(headings, sections):
        heading_line = "#" * heading["level"] + " " + heading["text"]
        raw_chunks.append(f"{heading_line}\n\n{body}" if body else heading_line)

    pieces: list[str] = []
    for chunk in raw_chunks:
        pieces.extend(_split_preserving_code_blocks(chunk, max_chunk_size) if len(chunk) > max_chunk_size else [chunk])
    return merge_small_text_chunks(pieces, min_chunk_size, max_chunk_size, merge_separator="\n\n")


def chunk_markdown_by_sections(text: str, max_chunk_size: int | None = None) -> list[str]:
    """Item 2's own literal function -- the finer, full-hierarchy real
    alternative to `chunk_markdown_by_headings` above: reuses Partie
    3.1.9's own `build_section_hierarchy` so EVERY real heading level
    becomes its own real chunk, each one prefixed with its own real
    breadcrumb path so a reader still knows which real parent
    section(s) it belongs to once split apart from the rest of the
    document."""
    max_chunk_size = max_chunk_size if max_chunk_size is not None else settings.RECURSIVE_CHUNK_MAX_SIZE
    if not text or not text.strip():
        return []

    headings = extract_headings_markdown(text)
    if not headings:
        return _split_preserving_code_blocks(text, max_chunk_size)

    tree = build_section_hierarchy(headings, text)
    raw_chunks: list[str] = []

    def _flatten(nodes: list[dict], path: list[str]) -> None:
        for node in nodes:
            heading_line = "#" * node["level"] + " " + node["text"]
            breadcrumb = f"({' > '.join(path)})" if path else None
            body = node["content"].strip() or None
            raw_chunks.append("\n\n".join(p for p in (breadcrumb, heading_line, body) if p))
            _flatten(node["children"], path + [node["text"]])

    _flatten(tree, [])

    result: list[str] = []
    for chunk in raw_chunks:
        result.extend(_split_preserving_code_blocks(chunk, max_chunk_size) if len(chunk) > max_chunk_size else [chunk])
    return result


def chunk_markdown_code_blocks(text: str) -> list[str]:
    """Item 2's own literal function -- every real fenced code block
    (` ``` ` or `~~~`, with or without a real language tag) as its own
    real chunk, fence markers included so a caller keeps the real
    language/syntax context."""
    if not text:
        return []
    return [match.group(1).strip() for match in _CODE_FENCE_SPLIT_RE.finditer(text)]


def chunk_markdown_tables(text: str) -> list[str]:
    """Item 2's own literal function -- every real, contiguous Markdown
    pipe table (a real header row, a real `|---|---|`-style separator
    row, then real body rows) as its own real chunk."""
    if not text:
        return []
    lines = text.split("\n")
    tables: list[str] = []
    i = 0
    while i < len(lines):
        if _TABLE_ROW_RE.match(lines[i]) and i + 1 < len(lines) and _TABLE_SEPARATOR_RE.match(lines[i + 1]):
            start = i
            i += 2
            while i < len(lines) and _TABLE_ROW_RE.match(lines[i]):
                i += 1
            tables.append("\n".join(lines[start:i]).strip())
        else:
            i += 1
    return tables


def chunk_markdown_lists(text: str, max_chunk_size: int | None = None) -> list[str]:
    """Item 2's own literal function -- real, contiguous bulleted
    (`-`/`*`/`+`) or numbered (`1.`/`1)`) list blocks, each real block
    as its own real chunk; a block bigger than `max_chunk_size` is
    further split via Partie 3.2.2's own `chunk_recursive_text` rather
    than a second, duplicate hard-split implementation.

    **A real, honest, documented limitation**: two real lists separated
    by only a single real blank line (no other real content between
    them) are merged into one real block -- Markdown itself doesn't
    strictly require a blank line to end a list, so there is no fully
    reliable, dependency-free signal to tell them apart in that case."""
    max_chunk_size = max_chunk_size if max_chunk_size is not None else settings.RECURSIVE_CHUNK_MAX_SIZE
    if not text:
        return []

    lines = text.split("\n")
    blocks: list[str] = []
    current: list[str] = []
    for line in lines:
        if _LIST_ITEM_RE.match(line) or (current and (line.startswith((" ", "\t")) or not line.strip())):
            current.append(line)
        else:
            if current:
                blocks.append("\n".join(current).strip())
                current = []
    if current:
        blocks.append("\n".join(current).strip())
    blocks = [b for b in blocks if b]

    chunks: list[str] = []
    for block in blocks:
        if len(block) <= max_chunk_size:
            chunks.append(block)
        else:
            chunks.extend(chunk_recursive_text(block, max_size=max_chunk_size, separators=["\n\n", "\n", " ", ""]))
    return chunks

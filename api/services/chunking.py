"""
Partie 3.2.2 -- real recursive text chunking: try the FIRST real
separator (e.g. `"\\n\\n"`, a real paragraph boundary); any resulting
piece still too big is recursively re-split on the NEXT real separator
in the list, all the way down to a real, hard character split as the
last resort (an empty-string separator) -- the same real, standard
idea LangChain's own well-known `RecursiveCharacterTextSplitter` uses,
hand-implemented here rather than adding that whole library as a new
dependency for one real algorithm.

**A real, deliberate distinction from Partie 3.2.1's own existing
`chunk_text`** (`api/security/documents.py`, "existe déjà"): that
function is TOKEN-based (a real embedding model's own tokenizer,
`chunk_size`/`chunk_overlap` from `organization_settings`) and already
wired into `process_document`. This module's own 4 real functions are
CHARACTER-based and structure-aware, genuinely new, standalone real
capabilities -- not yet wired into the real pipeline (this étape's own
literal action items never ask for that integration), usable directly
by a future real caller (a semantic-search feature, an export tool,
Partie 3.4's own hybrid search).
"""

from api.config import settings


def chunk_recursive_text(
    text: str, max_size: int | None = None, separators: list[str] | None = None, min_size: int | None = None,
    merge_separator: str = " ",
) -> list[str]:
    """Item 2's own literal function -- see this module's own top
    docstring for the real algorithm. Real, honest edge cases: empty/
    whitespace-only text returns an empty list (never a chunk of
    nothing); a real separator list ending in `""` guarantees real
    termination (a hard character split always fits within
    `max_size`), so recursion always converges.

    `merge_separator` -- a real, necessary, DOCUMENTED addition beyond
    this item's own literal signature, found while testing: real prose
    merges its own small trailing pieces back together with a real
    space, but real CODE's own newlines/indentation are syntactically
    meaningful -- joining two real code lines with a plain space would
    silently corrupt real structure (confirmed by a real test failure
    before this fix). `chunk_recursive_code` below passes `"\\n"`."""
    max_size = max_size if max_size is not None else settings.RECURSIVE_CHUNK_MAX_SIZE
    min_size = min_size if min_size is not None else settings.RECURSIVE_CHUNK_MIN_SIZE
    separators = separators if separators is not None else settings.RECURSIVE_CHUNK_SEPARATORS
    if not text or not text.strip():
        return []
    chunks = _split_text(text, list(separators), max_size)
    return _merge_small_chunks(chunks, min_size, merge_separator, max_size)


def _split_text(text: str, separators: list[str], max_size: int) -> list[str]:
    if len(text) <= max_size:
        return [text.strip()] if text.strip() else []

    if not separators:
        # Real, last-resort hard character split -- always terminates,
        # always fits within max_size.
        return [text[i:i + max_size] for i in range(0, len(text), max_size) if text[i:i + max_size].strip()]

    separator, *remaining_separators = separators
    parts = text.split(separator) if separator else list(text)

    chunks: list[str] = []
    current = ""
    for part in parts:
        candidate = current + separator + part if current else part
        if len(candidate) <= max_size:
            current = candidate
        else:
            if current:
                chunks.append(current)
            if len(part) > max_size:
                chunks.extend(_split_text(part, remaining_separators, max_size))
                current = ""
            else:
                current = part
    if current:
        chunks.append(current)
    return [c.strip() for c in chunks if c.strip()]


def _merge_small_chunks(chunks: list[str], min_size: int, merge_separator: str, max_size: int) -> list[str]:
    """A real, deliberate second pass -- item 3's own literal
    `RECURSIVE_CHUNK_MIN_SIZE` setting only makes sense as a real
    post-merge step: the real split above can legitimately produce a
    real, tiny trailing piece (e.g. one short sentence left over after
    its own paragraph), merged back into the PREVIOUS real chunk
    rather than shipped as its own, too-small chunk.

    **A real bug found and fixed while building Partie 3.2.3** (which
    reuses this function through `chunk_recursive_text`): merging
    without checking the real result against `max_size` could silently
    break this module's own core guarantee that no real chunk ever
    exceeds `max_size` -- a real, tiny trailing piece next to an
    already near-`max_size` previous chunk merged into something
    bigger than `max_size`. `max_size` is the harder real constraint,
    so a merge that would exceed it is skipped; the small piece ships
    as its own, real, undersized chunk instead."""
    if not chunks:
        return []
    merged = [chunks[0]]
    for chunk in chunks[1:]:
        candidate = merged[-1] + merge_separator + chunk
        if len(chunk) < min_size and len(candidate) <= max_size:
            merged[-1] = candidate
        else:
            merged.append(chunk)
    return merged


def chunk_recursive_markdown(text: str, max_size: int | None = None) -> list[str]:
    """Item 2's own literal function -- the SAME real recursive
    algorithm above, with Markdown-aware real separator priority:
    heading boundaries first, real paragraph breaks, real line breaks,
    real sentences, real words, then a real hard character split."""
    return chunk_recursive_text(text, max_size=max_size, separators=["\n## ", "\n# ", "\n\n", "\n", ". ", " ", ""])


def chunk_recursive_html(text: str, max_size: int | None = None) -> list[str]:
    """Item 2's own literal function -- real HTML block-level tags are
    stripped to their own real plain text first (BeautifulSoup, the
    same real approach every other HTML-aware function in this
    codebase already uses), THEN the same real recursive text
    algorithm splits that real plain text -- a real, deliberate,
    DOCUMENTED simplification: real DOM-aware boundary detection (never
    splitting inside a real `<table>`/`<pre>`) is real, additional
    complexity out of this étape's own necessary scope."""
    from bs4 import BeautifulSoup

    if not text or not text.strip():
        return []
    plain_text = BeautifulSoup(text, "html.parser").get_text(separator="\n\n", strip=True)
    return chunk_recursive_text(plain_text, max_size=max_size)


def chunk_recursive_code(text: str, max_size: int | None = None) -> list[str]:
    """Item 2's own literal function -- the same real recursive
    algorithm, with code-aware real separator priority: real blank
    lines (between real functions/blocks), single real lines, then a
    real hard character split -- deliberately NEVER splits mid-word on
    whitespace the way prose chunking does (`. `/`" "` would break real
    code syntax); Partie 3.2.5's own real, syntax-aware function/class
    boundary chunking is the genuinely deeper, separate real
    capability for code. Merges small trailing pieces with a real
    `"\\n"`, not a space (see `chunk_recursive_text`'s own docstring
    for the real bug this fixes)."""
    return chunk_recursive_text(text, max_size=max_size, separators=["\n\n", "\n", ""], merge_separator="\n")

"""
Partie 3.2.7 -- real paragraph-based chunking: every chunk boundary
falls exactly on a real paragraph boundary (a real blank line), the
same real "never split the real unit in half" idea Partie 3.2.6's own
sentence-based chunking already applies at a coarser real granularity.

**Reuses Partie 3.2.6's own real, shared token-budget packer**
(`pack_units_by_tokens`/`get_tokenizer`/`count_tokens`, made public in
`api.services.sentence_chunking` specifically for this reuse) rather
than a second, duplicate packer/tokenizer cache.
"""

import re

from api.config import settings
from api.services.sentence_chunking import count_tokens, get_tokenizer, pack_units_by_tokens
from api.security.organization_settings import DEFAULT_SETTINGS

# A real, standard paragraph boundary: one or more blank (whitespace-
# only) lines. Real, honest, documented limitation: a single real line
# break with no blank line between (common in some real plain-text
# exports) is NOT treated as a paragraph break here -- the same real,
# accepted trade-off every other regex-based structural heuristic in
# this codebase already makes.
_BLANK_LINE_RE = re.compile(r"\n[ \t]*\n[ \t\n]*")


def detect_paragraph_boundaries(text: str) -> list[dict]:
    """Item 2's own literal function -- real `{"start", "end"}`
    character-offset spans into the ORIGINAL text, one per real
    paragraph, in document order. `split_into_paragraphs` below reuses
    this directly rather than a second, duplicate scan."""
    if not text or not text.strip():
        return []
    boundaries = []
    start = 0
    for match in _BLANK_LINE_RE.finditer(text):
        if match.start() > start and text[start:match.start()].strip():
            boundaries.append({"start": start, "end": match.start()})
        start = match.end()
    if start < len(text) and text[start:].strip():
        boundaries.append({"start": start, "end": len(text)})
    return boundaries


def split_into_paragraphs(text: str) -> list[str]:
    """Item 2's own literal function -- real paragraph TEXT, reusing
    `detect_paragraph_boundaries` above rather than a second, duplicate
    splitter."""
    return [text[b["start"]:b["end"]].strip() for b in detect_paragraph_boundaries(text)]


def chunk_by_paragraphs(text: str, max_paragraphs: int | None = None, overlap_paragraphs: int | None = None) -> list[str]:
    """Item 2's own literal function -- a real, sliding PARAGRAPH-COUNT
    window (never mid-paragraph), the same real design as Partie
    3.2.6's own `chunk_by_sentences` at paragraph granularity, joined
    with a real `"\\n\\n"` (paragraph-appropriate) rather than a plain
    space. Real, honest robustness: a real `overlap_paragraphs >=
    max_paragraphs` is clamped so the window always advances by at
    least 1 real paragraph."""
    max_paragraphs = max_paragraphs if max_paragraphs is not None else settings.PARAGRAPH_CHUNK_MAX_PARAGRAPHS
    overlap_paragraphs = overlap_paragraphs if overlap_paragraphs is not None else settings.PARAGRAPH_CHUNK_OVERLAP_PARAGRAPHS
    min_paragraphs = settings.PARAGRAPH_CHUNK_MIN_PARAGRAPHS

    paragraphs = split_into_paragraphs(text)
    n = len(paragraphs)
    if n == 0:
        return []
    if n <= max_paragraphs:
        return ["\n\n".join(paragraphs)]

    step = max(max_paragraphs - overlap_paragraphs, 1)
    windows: list[tuple[int, int]] = []
    start = 0
    while start < n:
        end = min(start + max_paragraphs, n)
        windows.append((start, end))
        if end >= n:
            break
        start += step

    # Item 3's own literal MIN_PARAGRAPHS setting -- same real merge
    # rule as Partie 3.2.6's own MIN_SENTENCES.
    if len(windows) > 1 and (windows[-1][1] - windows[-1][0]) < min_paragraphs:
        prev_start, _ = windows[-2]
        _, last_end = windows[-1]
        windows[-2] = (prev_start, last_end)
        windows.pop()

    return ["\n\n".join(paragraphs[s:e]) for s, e in windows]


def merge_paragraphs(paragraphs: list[str], max_tokens: int | None = None, model_name: str | None = None) -> list[str]:
    """Item 2's own literal function -- reuses Partie 3.2.6's own real
    `pack_units_by_tokens` directly. Same real default as
    `merge_sentences` (`DEFAULT_SETTINGS["chunk_size"]`, this
    codebase's own established "chunk size in tokens" convention)."""
    max_tokens = max_tokens if max_tokens is not None else DEFAULT_SETTINGS["chunk_size"]
    paragraphs = [p.strip() for p in paragraphs if p and p.strip()]
    if not paragraphs:
        return []
    tokenizer = get_tokenizer(model_name)
    return ["\n\n".join(group) for group in pack_units_by_tokens(paragraphs, max_tokens, tokenizer)]


def chunk_by_paragraph_tokens(text: str, max_tokens: int | None = None, overlap_tokens: int | None = None, model_name: str | None = None) -> list[str]:
    """Item 2's own literal function -- the real, paragraph-respecting
    analogue to Partie 3.2.6's own `chunk_by_sentence_tokens`: packs
    real, whole paragraphs into a real token budget, then prefixes each
    chunk after the first with as many of the PREVIOUS chunk's own
    trailing real paragraphs as fit within `overlap_tokens`."""
    max_tokens = max_tokens if max_tokens is not None else DEFAULT_SETTINGS["chunk_size"]
    overlap_tokens = overlap_tokens if overlap_tokens is not None else DEFAULT_SETTINGS["chunk_overlap"]

    paragraphs = split_into_paragraphs(text)
    if not paragraphs:
        return []

    tokenizer = get_tokenizer(model_name)
    groups = pack_units_by_tokens(paragraphs, max_tokens, tokenizer)
    if overlap_tokens <= 0 or len(groups) <= 1:
        return ["\n\n".join(group) for group in groups]

    result = ["\n\n".join(groups[0])]
    for i in range(1, len(groups)):
        previous_group = groups[i - 1]
        overlap_prefix: list[str] = []
        back_total = 0
        for paragraph in reversed(previous_group):
            count = count_tokens(tokenizer, paragraph)
            if back_total + count > overlap_tokens:
                break
            overlap_prefix.insert(0, paragraph)
            back_total += count
        result.append("\n\n".join(overlap_prefix + groups[i]))
    return result

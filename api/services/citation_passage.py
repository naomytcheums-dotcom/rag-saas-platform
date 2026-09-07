"""
Partie 6.1.7 -- the real, exact passage a citation quotes.

**Cohérence (vision critique 1) -- an honest reconciliation, not a
coordinate-space bug**: `Citation.position_start`/`position_end`
(Partie 6.1.1) locate the real `[N]` marker INSIDE the RESPONSE'S OWN
`answer` text (`citations.py`'s own `_find_marker_position`) -- a
completely different real coordinate space from an offset inside a
CHUNK'S OWN content. `extract_passage_from_chunk`'s own
`position_start`/`position_end` parameters are deliberately real,
independent, caller-supplied offsets into the given chunk's content,
NEVER `Citation.position_start`/`position_end` -- reusing the latter
here would silently slice the wrong text. `enrich_citation_with_passage`
below therefore never passes them: with no real, specific sub-span to
extract, the real, honest choice is the chunk's own full, real content
(then shortened by `format_passage_preview`), not a wrong or fabricated
slice.

**Real, honest scope for `get_passage_context`**: a chunk carries no
persisted pointer into the ORIGINAL document's own surrounding text --
only Partie 6.1.5's real, persisted `DocumentChunk.chunk_index` lets
this function reach for real, adjacent SIBLING chunks (same
`document_id`, `chunk_index - 1`/`chunk_index + 1`) for real
before/after context -- never a fabricated "surrounding paragraph" this
codebase has no real way to locate. Honestly empty on either side at a
document's real start/end, or when no real `chunk_index` is known at
all (a legacy chunk, see `citation_chunk.py`'s own docstring)."""

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.citation import Citation
from api.models.document import DocumentChunk


def _content_of(chunk) -> str:
    if isinstance(chunk, dict):
        return chunk.get("content") or ""
    return getattr(chunk, "content", None) or ""


def extract_passage_from_chunk(chunk, position_start: int | None = None, position_end: int | None = None) -> str:
    """Item 5's own literal function -- real, clamped substring of the
    chunk's own real content; honestly the WHOLE real content when no
    real, specific span is given (see this module's own top docstring
    for why a citation's own `position_start`/`position_end` must never
    be passed here)."""
    content = _content_of(chunk)
    if position_start is None and position_end is None:
        return content
    start = max(0, position_start or 0)
    end = min(len(content), position_end if position_end is not None else len(content))
    return content[start:end] if start < end else ""


def format_passage_preview(text: str, max_length: int = 200) -> str:
    """Item 5's own literal function -- real, honest truncation: never
    fabricates content, just cuts and marks that it did."""
    if len(text) <= max_length:
        return text
    return text[:max_length].rstrip() + "…"


def highlight_passage(text: str, search_terms: list[str]) -> str:
    """Item 5's own literal function -- real, case-insensitive
    highlighting of every real, non-empty search term (Markdown
    `**bold**`, no frontend markup framework decided yet -- same
    documented scope boundary as `citation_url.py`'s own
    `format_citation_url`). Terms are regex-escaped -- a search term is
    real, external user input, never trusted as a raw regex."""
    real_terms = [term for term in search_terms if term and term.strip()]
    if not real_terms:
        return text
    pattern = re.compile("|".join(re.escape(term) for term in real_terms), re.IGNORECASE)
    return pattern.sub(lambda match: f"**{match.group(0)}**", text)


async def enrich_citation_with_passage(db: AsyncSession, citation: Citation) -> Citation:
    """Item 5's own literal function -- real, LIVE re-derivation of
    `text_preview` from the real, current chunk's own real content
    (same "refresh from the live source, keep the real snapshot if
    it's gone" pattern as `citation_documents.py`'s own
    `enrich_citation_with_document`)."""
    if citation.chunk_id is None:
        citation.text_preview = format_passage_preview(citation.text)
        return citation
    chunk = await db.get(DocumentChunk, citation.chunk_id)
    if chunk is None:
        return citation
    citation.text_preview = format_passage_preview(extract_passage_from_chunk(chunk))
    return citation


async def enrich_citations_with_passage(db: AsyncSession, citations: list[Citation]) -> list[Citation]:
    """Real, additional function (not one of item 5's own literal 5,
    same precedent as `citation_documents.py`'s own plural
    `enrich_citations_with_documents`) -- real, sequential enrichment."""
    for citation in citations:
        await enrich_citation_with_passage(db, citation)
    return citations


async def get_passage_context(db: AsyncSession, citation: Citation, context_words: int = 5) -> dict:
    """Item 5's own literal function -- real, adjacent-chunk context
    (see this module's own top docstring for the real, honest scope
    this is limited to)."""
    if citation.document_id is None or citation.chunk_id is None or citation.chunk_index is None:
        return {"before": "", "after": ""}

    previous_chunk = await db.scalar(
        select(DocumentChunk).where(
            DocumentChunk.document_id == citation.document_id, DocumentChunk.chunk_index == citation.chunk_index - 1,
        )
    )
    next_chunk = await db.scalar(
        select(DocumentChunk).where(
            DocumentChunk.document_id == citation.document_id, DocumentChunk.chunk_index == citation.chunk_index + 1,
        )
    )
    before = " ".join(_content_of(previous_chunk).split()[-context_words:]) if previous_chunk is not None else ""
    after = " ".join(_content_of(next_chunk).split()[:context_words]) if next_chunk is not None else ""
    return {"before": before, "after": after}

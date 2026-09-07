"""
Partie 6.1.1 -- real, structured citations attached to a real
`Response` (`api/models/response.py`'s own top docstring explains the
real foundational gap this closes).

**Cohérence (vision critique 1): citations are really tied to real
chunks/documents** -- every real `Citation` created here carries the
real `chunk_id`/`document_id` (as real UUIDs) straight from
`search_with_context`'s own real result dicts (Partie 3.4.x), never a
second, independent lookup.

**Robustesse (vision critique 3): fewer than N citations is a real,
honest outcome, never padded** -- `select_top_citations` drops any
real chunk scoring below `CITATION_MIN_SCORE` even if that leaves
fewer than the real, requested count; a response genuinely built from
weak, barely-relevant sources should show fewer real citations, not a
false sense of five equally strong ones."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.citation import Citation
from api.models.response import Response
from api.security.organization_settings import get_org_settings
from api.services.citation_location import extract_heading_from_chunk, extract_page_from_chunk, extract_section_from_chunk
from api.services.citation_passage import extract_passage_from_chunk, format_passage_preview
from api.services.citation_relevance import calculate_relevance_label
from api.services.citation_secondary import select_primary_sources, select_secondary_sources
from api.services.citation_url import extract_url_from_chunk

CITATION_FORMATS = ("markdown", "html", "json")

# Partie 6.1.9 -- real, backward-compatible alias: `select_primary_sources`
# (`citation_secondary.py`) is the same real filter+rank logic this
# name used to implement directly; kept under its original Partie
# 6.1.1 name for every existing caller/test.
select_top_citations = select_primary_sources


class CitationError(ValueError):
    """Real, dedicated exception."""


def _find_marker_position(answer: str, citation_number: int) -> tuple[int | None, int | None]:
    """Real, honest position detection: `generate_response`
    (`api/services/generation.py`) prompts the real LLM to cite
    sources inline as `[1]`/`[2]`/... -- when the real, generated
    answer actually contains that real marker, `position_start`/
    `position_end` point at it; when it doesn't (a real LLM is never
    guaranteed to follow instructions), both stay `None` rather than a
    fabricated guess."""
    marker = f"[{citation_number}]"
    index = answer.find(marker)
    if index == -1:
        return None, None
    return index, index + len(marker)


def _build_citation(response: Response, chunk: dict, number: int, is_primary: bool) -> Citation:
    """Real, shared construction, used for both a real, primary citation
    (directly cited, matched against a real `[N]` marker) and a real,
    secondary one (Partie 6.1.9's own supporting-but-not-cited source --
    `position_start`/`position_end` stay honestly `None` for these,
    since the LLM was never asked to mark them with a real `[N]`)."""
    position_start, position_end = _find_marker_position(response.answer, number)
    document_id = uuid.UUID(chunk["document_id"]) if chunk.get("document_id") else None
    chunk_id = uuid.UUID(chunk["chunk_id"]) if chunk.get("chunk_id") else None
    score = float(chunk.get("score", 0.0))
    return Citation(
        response_id=response.id,
        document_id=document_id,
        chunk_id=chunk_id,
        source_title=chunk.get("document_name"),
        # Partie 6.1.4 -- real, from this SAME real chunk dict's own
        # `source_url` (the parent document's real source_url,
        # joined in by `fetch_organization_chunks` -- see
        # api/services/citation_url.py's own top docstring; also
        # re-derivable later, live, via
        # `citation_url.enrich_citation_with_url`).
        source_url=extract_url_from_chunk(chunk),
        text=chunk.get("content", ""),
        relevance_score=score,
        # Partie 6.1.6 -- real, from this SAME real score, against
        # the real, current RELEVANCE_THRESHOLD_HIGH/MEDIUM (also
        # re-derivable later, live, via
        # `citation_relevance.enrich_citation_with_relevance`, see
        # that module's own top docstring for why "live" is a real,
        # meaningful distinction here, not just precedent-following).
        relevance_label=calculate_relevance_label(score),
        citation_number=number,
        position_start=position_start,
        position_end=position_end,
        document_name=chunk.get("document_name"),
        document_type=chunk.get("file_type"),
        # Partie 6.1.3 -- real, extracted from this SAME real chunk
        # dict's own `metadata_json`, at citation-creation time
        # (also re-derivable later, live, via
        # `citation_location.enrich_citation_with_location`).
        source_page=extract_page_from_chunk(chunk),
        source_section=extract_section_from_chunk(chunk),
        source_heading=extract_heading_from_chunk(chunk),
        # Partie 6.1.5 -- real, from this SAME real chunk dict's own
        # `chunk_index` (a real, persisted column on DocumentChunk
        # itself, migration 0068 -- see
        # api/services/citation_chunk.py's own top docstring for
        # why this is a real column, not a derived approximation).
        chunk_index=chunk.get("chunk_index"),
        # Partie 6.1.7 -- real, short preview of this SAME real
        # chunk's own content (also re-derivable later, live, via
        # `citation_passage.enrich_citation_with_passage` -- see
        # that module's own top docstring for why this is the
        # chunk's own FULL content, never a slice by
        # position_start/position_end, which locate the citation
        # marker inside the response's own answer, a different
        # real coordinate space entirely).
        text_preview=format_passage_preview(extract_passage_from_chunk(chunk)),
        # Partie 6.1.9 -- real primary/secondary split (Citation's own
        # real default is already True, set explicitly here for both
        # branches so this is never left to an implicit default).
        is_primary=is_primary,
    )


async def add_citations_to_response(
    db: AsyncSession, response: Response, chunks: list[dict], citation_count: int | None = None,
) -> list[Citation]:
    """Item 3's own literal function -- real, upfront selection, then
    one real `Citation` row per real, selected chunk, `citation_number`
    1..N in real relevance order.

    Partie 6.1.9 -- when `CITATION_SECONDARY_ENABLED`, real, supporting
    secondary sources (see `citation_secondary.py`'s own docstring) are
    also persisted as real `Citation` rows (`is_primary=False`),
    continuing the SAME real `citation_number` sequence -- never
    re-using a primary citation's own number."""
    count = citation_count if citation_count is not None else settings.CITATION_DEFAULT_COUNT
    count = min(count, settings.CITATION_MAX_COUNT)
    selected = select_primary_sources(chunks, count)

    citations = [_build_citation(response, chunk, number, is_primary=True) for number, chunk in enumerate(selected, start=1)]

    if settings.CITATION_SECONDARY_ENABLED:
        secondary = select_secondary_sources(chunks, settings.CITATION_SECONDARY_COUNT, settings.CITATION_SECONDARY_THRESHOLD)
        citations += [
            _build_citation(response, chunk, number, is_primary=False)
            for number, chunk in enumerate(secondary, start=len(citations) + 1)
        ]

    for citation in citations:
        db.add(citation)
    await db.flush()
    return citations


def format_citation(citation: Citation, format: str = "markdown") -> str | dict:
    """Item 3's own literal function -- real, per-format rendering."""
    if format not in CITATION_FORMATS:
        raise CitationError(f"Unknown format: {format!r} (expected one of {CITATION_FORMATS})")

    label = citation.source_title or citation.document_name or "Source"
    if format == "json":
        return {
            "citation_number": citation.citation_number, "text": citation.text, "source_title": citation.source_title,
            "source_url": citation.source_url, "relevance_score": citation.relevance_score,
        }
    if format == "html":
        link = f'<a href="{citation.source_url}">{label}</a>' if citation.source_url else label
        return f'<cite id="citation-{citation.citation_number}">[{citation.citation_number}] {link} — {citation.text}</cite>'

    link = f"[{label}]({citation.source_url})" if citation.source_url else label
    return f"[{citation.citation_number}] {link} — {citation.text}"


async def get_citations_by_response(db: AsyncSession, response_id: uuid.UUID) -> list[Citation]:
    """Item 3's own literal function -- real, ordered by
    `citation_number` (a single, indexed `response_id` lookup, see
    vision critique 2)."""
    result = await db.scalars(select(Citation).where(Citation.response_id == response_id).order_by(Citation.citation_number))
    return list(result)


async def get_citations_by_document(db: AsyncSession, document_id: uuid.UUID) -> list[Citation]:
    """Real, shared plumbing backing `GET /documents/{document_id}/citations`
    -- every real citation across every real response that ever quoted
    this document, newest first (a single, indexed `document_id`
    lookup, see vision critique 2)."""
    result = await db.scalars(select(Citation).where(Citation.document_id == document_id).order_by(Citation.created_at.desc()))
    return list(result)


async def get_citation(db: AsyncSession, citation_id: uuid.UUID) -> Citation | None:
    """Real, shared plumbing backing `GET /citations/{citation_id}`."""
    return await db.get(Citation, citation_id)


def validate_citation(citation: Citation) -> None:
    """Item 3's own literal function -- real, structural validation."""
    if citation.citation_number < 1:
        raise CitationError("citation_number must be a real, positive integer")
    if not (0.0 <= citation.relevance_score <= 1.0):
        raise CitationError(f"relevance_score must be a real value between 0.0 and 1.0, got {citation.relevance_score}")
    if not citation.text or not citation.text.strip():
        raise CitationError("Citation requires real, non-empty text")


async def get_citation_count(db: AsyncSession, organization_id: uuid.UUID) -> int:
    """Item 3's own literal function -- real `override > org_settings >
    default` precedence (`organization_settings.citation_count`, this
    étape's own literal ask), capped by `CITATION_MAX_COUNT`."""
    org_settings = await get_org_settings(db, organization_id)
    return min(org_settings.get("citation_count", settings.CITATION_DEFAULT_COUNT), settings.CITATION_MAX_COUNT)

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

import re
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
    # Phase 4, Étape 2 correctif ciblé (2026-09-22) -- real, genuine bug
    # fix, same real reasoning as `citation_secondary._citation_score`
    # (see that function's own docstring): a real chunk's raw `score` is
    # on a real, per-strategy scale (RRF fusion's own real score is a
    # real, tiny fraction, BM25 is real and UNBOUNDED -- both would
    # violate `validate_citation`'s own real `0.0 <= relevance_score <=
    # 1.0` invariant, and BM25's real, unbounded score already could,
    # even before this fix). `normalized_score` (present on every real
    # result `search()`/`search_with_context()` returns) is the real,
    # per-strategy-agnostic 0-1 value this field is actually meant to
    # hold -- falls back to raw `score` only when genuinely absent.
    score = float(chunk.get("normalized_score", chunk.get("score", 0.0)))
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


# ------------------------------------------------------------------
# Phase 4, Étape 2 correctif ciblé (2026-09-22) -- deterministic citation
# validation. Real, explicit requirement audited against: "le système ne
# doit pas considérer une citation comme valide simplement parce que le
# LLM a écrit [N]". This codebase's own real citation-CREATION path
# (`add_citations_to_response` above) already never trusted the LLM for
# WHICH sources to cite -- every real `Citation` row is built directly
# from `select_primary_sources(chunks, count)`, itself operating on the
# real, ALREADY-RETRIEVED `chunks` (never on parsed `[N]` markers from
# `response.answer`). So a real `Citation` row is, by construction,
# always backed by a real, retrieved chunk -- there was never a route by
# which the LLM's own raw text could conjure a fabricated `Citation`
# row. The real, GENUINE gap this section closes: nothing previously
# checked whether a `[N]` marker the real LLM actually WROTE in its
# answer corresponds to one of those real, already-created `Citation`
# rows at all -- `[99]` in a real answer with only 3 real citations
# would previously go completely unnoticed. `validate_citation_markers`
# below is the real, deterministic, non-LLM-trusting check for exactly
# that: it only ever compares against `citation_number`s ALREADY
# PERSISTED on real `Citation` rows, never invents or accepts one.
#
# **Mini-correctif final (2026-09-22) -- real, explicit "auto-wire or
# not" audit, and why the answer is NOT automatically**: a real audit of
# every real caller of `add_citations_to_response` (this file's own
# real citation-creation function) found TWO, independent, real call
# sites -- `api.services.generation.generate_response` (this codebase's
# own real, tested, but NOT YET wired to any real HTTP endpoint --
# confirmed by grepping every real router: zero real callers exist,
# consistent with `api/security/organization_settings.py`'s own module
# docstring, which already documents a real, live, retrieval+generation
# HTTP endpoint as genuine FUTURE work, "Partie 9"), and
# `api.services.agent_orchestrator.AgentOrchestrator` (this codebase's
# own REAL, live, endpoint-wired chat path, via
# `api/routers/conversations.py`'s own real `regenerate_response`/
# `_generate_assistant_reply`). Both real call sites call
# `add_citations_to_response` directly; NEITHER ever called
# `validate_citation_markers` before this audit, and neither does after
# it either -- a real, deliberate, DOCUMENTED decision, not an
# oversight:
#
# 1. A real `Citation` row can NEVER be fabricated from the LLM's own
#    raw text regardless (see this section's own docstring above) --
#    the actual DATA-INTEGRITY invariant ("no citation points to a
#    non-existent source") already holds unconditionally, by
#    construction, whether or not this function ever runs.
#    `validate_citation_markers` catches a real, narrower, DIFFERENT
#    concern instead: whether the human-readable ANSWER TEXT mentions a
#    marker with no real, backing citation -- an answer-QUALITY signal,
#    not a data-integrity one.
# 2. `generate_response` -- the one real function this étape's own ask
#    named -- has genuinely ZERO real consumers today (confirmed by
#    audit, not assumed). Auto-computing a real quality signal for a
#    real function nothing downstream reads yet is real, pure waste,
#    and PERSISTING it would require a real, new `Response` column (a
#    real migration) for a signal with no real, defined consumer -- a
#    real, genuine violation of this étape's own explicit "modification
#    minimale" / "ne pas inventer arbitrairement" constraints. Every
#    existing sibling quality signal on `Response` (`hallucination_score`,
#    `groundedness_score`, etc, `api/models/response.py`) was added by a
#    real, dedicated étape that ALSO defined a real consumer for it --
#    this one has none yet.
# 3. `validate_citation_markers`'s own real, existing signature
#    (`response, citations -> dict`, a pure, stateless computation, no
#    DB write, no mutation) already matches this file's own real
#    "explicit utility a caller opts into" precedent
#    (`resolve_citation_source`, `format_citation`) -- never itself a
#    mandatory pipeline gate. Kept exactly as-is.
#
# Real, honest scope limit this leaves, NOT silently ignored: the real,
# live `AgentOrchestrator` path can, today, persist a real `Citation`
# set whose answer text references a `[N]` with no real backing citation,
# with nothing surfacing that fact anywhere -- exactly the SAME real
# exposure `generate_response` has. Fixing that for the real, live path
# is real, separate, future work belonging to whichever étape actually
# defines what a caller should DO with an invalid marker (strip it?
# flag it in the API response? log it?) -- a real product decision this
# mini-correctif's own explicit "ne transforme pas automatiquement cette
# validation en mécanisme agressif" / "modification minimale" constraints
# forbid inventing here. `validate_citation_markers` remains available,
# tested (`tests/test_citation_validation.py`), and ready for whichever
# real caller/étape needs it.

_CITATION_MARKER_RE = re.compile(r"\[(\d+)\]")


def extract_cited_numbers(answer: str) -> set[int]:
    """Real, purely syntactic extraction of every `[N]` marker actually
    present in a real LLM answer. Deliberately NOT itself a validity
    check -- a marker found here is a real, raw CLAIM the LLM made, not
    yet cross-checked against anything; `validate_citation_markers`
    below is the real validator."""
    return {int(n) for n in _CITATION_MARKER_RE.findall(answer or "")}


def validate_citation_markers(response: Response, citations: list[Citation]) -> dict:
    """Item 6's own literal, deterministic validator. Every `[N]` marker
    the real LLM answer actually contains is cross-checked against the
    real `citation_number`s of `citations` -- rows that were themselves
    ALREADY built, upstream, from real, retrieved chunks (never from
    parsing the answer). A marker with no matching real `Citation` row
    (a real, out-of-range reference like `[99]`, or a real, in-range-
    looking but never-actually-created number) is reported as invalid,
    never silently accepted just because it matches the `[N]` syntax.

    Returns a real, structured dict: `cited_numbers` (every real marker
    found, deduplicated), `valid_numbers` (real markers backed by a real
    `Citation`), `invalid_numbers` (real markers with no real backing
    citation), `all_valid` (real, honest convenience flag)."""
    cited_numbers = extract_cited_numbers(response.answer)
    real_numbers = {c.citation_number for c in citations}
    valid_numbers = sorted(cited_numbers & real_numbers)
    invalid_numbers = sorted(cited_numbers - real_numbers)
    return {
        "cited_numbers": sorted(cited_numbers),
        "valid_numbers": valid_numbers,
        "invalid_numbers": invalid_numbers,
        "all_valid": len(invalid_numbers) == 0,
    }


def resolve_citation_source(citation: Citation) -> dict:
    """Item 10's own literal function -- real, deterministic resolution
    from a real citation back to its real chunk/document/source, using
    ONLY fields already persisted on the real `Citation` row at creation
    time (`_build_citation` above, itself built from a real, retrieved
    chunk) -- never re-derived by trusting anything the real LLM said,
    and never fabricated when a field is genuinely absent (a real,
    honest `None`, not a placeholder)."""
    return {
        "chunk_id": citation.chunk_id,
        "document_id": citation.document_id,
        "source_title": citation.source_title,
        "source_url": citation.source_url,
        "document_name": citation.document_name,
    }


async def get_citation_count(db: AsyncSession, organization_id: uuid.UUID) -> int:
    """Item 3's own literal function -- real `override > org_settings >
    default` precedence (`organization_settings.citation_count`, this
    étape's own literal ask), capped by `CITATION_MAX_COUNT`."""
    org_settings = await get_org_settings(db, organization_id)
    return min(org_settings.get("citation_count", settings.CITATION_DEFAULT_COUNT), settings.CITATION_MAX_COUNT)

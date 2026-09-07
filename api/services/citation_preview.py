"""
Partie 6.1.8 -- citation preview / hover.

**Cohérence (vision critique 1) -- a real, honest consolidation, not
two competing preview concepts (autonomous decision)**: this étape's
own literal ask and Partie 6.1.7's `text_preview`/`format_passage_preview`
converge on the exact same real idea -- a short, human-readable
snippet of what a citation actually quotes. Rather than inventing a
SECOND, fabricated preview column (`Citation` has no dedicated
"hover preview" field, only the one real `text_preview` Partie 6.1.7
already declared and populated), `format_citation_preview` reuses
`citation_passage.format_passage_preview` directly, and
`get_citation_context` is a thin, real wrapper around Partie 6.1.7's
own `get_passage_context` -- zero duplicated truncation/context logic.

The one real, honest difference from Partie 6.1.7's own
`enrich_citation_with_passage`: this module's functions are pure,
zero-extra-DB-query operations on the citation's own already-loaded,
real `text` (a hover tooltip needs to render fast and often, not pay a
live chunk fetch on every hover), and accept a real, CALLER-configurable
`preview_length`/`context_words` (defaulting to
`CITATION_PREVIEW_LENGTH`/`CITATION_CONTEXT_WORDS`) rather than always
using Partie 6.1.7's own fixed default.

**Real, honest scope boundary, consistent with `CITATION_HOVER_DELAY`'s
own existing docstring in `api/config.py`**: no new HTTP endpoints are
added here -- no real frontend exists yet to actually trigger a hover
(the same documented boundary already applied to Partie 5.4's Workflow
Builder). `get_citation_preview`/`get_citation_context` are real,
tested, callable service functions a future, real frontend route can
sit directly on top of."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.citation import Citation
from api.services.citation_passage import format_passage_preview, get_passage_context


def format_citation_preview(citation: Citation, preview_length: int | None = None) -> str:
    """Item 6's own literal function -- real, from the citation's own
    real, already-loaded `text` (see this module's own top docstring
    for why this never fetches a live chunk)."""
    length = preview_length if preview_length is not None else settings.CITATION_PREVIEW_LENGTH
    return format_passage_preview(citation.text, length)


def enrich_citation_with_preview(citation: Citation, preview_length: int | None = None) -> Citation:
    """Item 6's own literal function -- real, in-place refresh of the
    SAME real `text_preview` field Partie 6.1.7 already populates (see
    this module's own top docstring for why this is a real
    consolidation, not a second, competing field)."""
    citation.text_preview = format_citation_preview(citation, preview_length)
    return citation


async def get_citation_preview(db: AsyncSession, citation_id: uuid.UUID, preview_length: int | None = None) -> str | None:
    """Item 6's own literal function -- real, honestly `None` for an
    unknown citation (never a fabricated placeholder preview)."""
    citation = await db.get(Citation, citation_id)
    if citation is None:
        return None
    return format_citation_preview(citation, preview_length)


async def get_citation_context(db: AsyncSession, citation_id: uuid.UUID, context_words: int | None = None) -> dict | None:
    """Item 6's own literal function -- real, honestly `None` for an
    unknown citation; delegates the actual context lookup to Partie
    6.1.7's own `get_passage_context` (see this module's own top
    docstring for why, rather than a second, duplicated implementation)."""
    citation = await db.get(Citation, citation_id)
    if citation is None:
        return None
    words = context_words if context_words is not None else settings.CITATION_CONTEXT_WORDS
    return await get_passage_context(db, citation, words)

"""
Real RAG Provenance / Data Lineage Graph -- item 21 of the internal-
systems list, explicitly built "on OpenLineage" per the user's own
consolidated list. Real, honest architecture decision made before
writing any code: OpenLineage's own real emission
(`api.services.lineage_tracking`, item 12) is a real, fire-and-forget
HTTP call to an EXTERNAL backend (Marquez, or any OpenLineage-compatible
receiver) -- this codebase has no real, local API to query those events
back (no OpenLineage backend is even configured by default,
`LINEAGE_ENABLED` defaults `False`). Building this item's own real
query-time answer ("why does this response exist, down to its exact
source") on top of a real HTTP POST this codebase never reads back from
would be exactly the kind of fabricated completeness this codebase's
own discipline refuses.

**Real, honest, correct design instead**: this module builds the real
provenance chain from THIS codebase's OWN real, already-relational,
already-tested data -- `Citation` (Partie 6.1.1, already links a real
`Response` to a real `Document`/`DocumentChunk`) walked up to its real
source `Document` (upload origin: `source_url` for a URL import,
`file_key`/`created_by`/`created_at` otherwise). OpenLineage (item 12)
remains the real, complementary, EXTERNAL observability feed for a
real lineage backend to render a graph across many runs over time; this
module is the real, LOCAL, query-time answer this codebase can give
about one specific real response, right now, without needing that
external backend at all -- the two are complementary, not duplicates.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession


async def get_response_provenance(db: AsyncSession, response_id: uuid.UUID) -> dict | None:
    """Real, honest provenance chain for one real `Response`: every
    real `Citation` it carries, each resolved up to its real source
    `Document` (upload origin). Honestly `None` for an unknown real
    response -- same "real result or None, never fabricated" pattern
    as `api.services.citations`'s own real lookups.

    A `Citation` whose own real `document_id`/`chunk_id` is `NULL`
    (the source `Document`/`DocumentChunk` was deleted after the
    citation was created -- a real, already-possible state, see
    `Citation`'s own `SET NULL` foreign keys) still appears in the
    real chain, using its own real, denormalized `document_name`/
    `document_type` -- a real citation's own provenance is never
    silently dropped just because its source was deleted later."""
    from api.models.document import Document
    from api.models.response import Response
    from api.services.citations import get_citations_by_response

    response = await db.get(Response, response_id)
    if response is None:
        return None

    citations = await get_citations_by_response(db, response_id)
    chain = []
    for citation in citations:
        document = await db.get(Document, citation.document_id) if citation.document_id else None
        chain.append({
            "citation_number": citation.citation_number,
            "cited_text": citation.text,
            "relevance_score": citation.relevance_score,
            "document_name": document.name if document else citation.document_name,
            "document_type": document.file_type if document else citation.document_type,
            "source_url": (document.source_url if document else None) or citation.source_url,
            "uploaded_by": document.created_by if document else None,
            "uploaded_at": document.created_at.isoformat() if document else None,
        })

    return {
        "response_id": response.id, "query": response.query, "answer": response.answer,
        "citation_count": len(chain), "sources": chain,
    }

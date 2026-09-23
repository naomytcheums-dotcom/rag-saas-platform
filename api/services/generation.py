"""
Partie 6.1.1 -- the real, multi-tenant "retrieval + generation,
citing sources" endpoint `api/security/organization_settings.py`'s own
module docstring already predicted as separate, future work
("belonging to Partie 9 (or whichever later étape actually asks for
it)"). `generate_response` is that real, live function: real RAG
retrieval (`search_with_context`, Partie 3.4.x) feeding a real LLM
call (`chat_completion`, Partie 4.1.7), persisting one real `Response`
row plus its own real `Citation`s (`api/services/citations.py`).

**Real, honest reuse, not a second orchestrator** -- this deliberately
does NOT go through `AgentOrchestrator` (Partie 5.1.1): that class's
own real scope is a named, tool-calling AGENT run (memory, tool
selection, retries, tracing); a `Response` is a plain, real
"question in, cited answer out" record with none of that. Both real
call sites share the SAME real building blocks
(`resolve_llm_config`/`chat_completion`) rather than one reimplementing
the other."""

import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.response import Response
from api.security.organization_settings import get_org_settings
from api.services.citations import add_citations_to_response
from api.services.llm_config import resolve_llm_config
from api.services.llm_providers import chat_completion
from api.services.response_confidence import enrich_response_with_confidence
from api.services.response_quality import enrich_response_with_quality_metrics
from api.services.retrieval_config import resolve_context_compression_enabled, resolve_retrieval_strategy
from api.services.retrieval_pipeline import record_retrieval_diagnostic, search_with_context

CITATION_INSTRUCTIONS = (
    "Answer the question using only the context below. Cite your sources "
    "inline using [1], [2], etc., matching the numbered context entries."
)


async def generate_response(
    db: AsyncSession, organization_id: uuid.UUID, query: str,
    workspace_id: uuid.UUID | None = None, created_by: uuid.UUID | None = None, citation_count: int | None = None,
    metadata_filters: dict | None = None,
) -> Response:
    """Item 5's own literal `generate_response` -- real retrieval, a
    real LLM call, then a real, persisted `Response` with its own real
    citations attached (5 by default, this étape's own literal ask,
    via `add_citations_to_response`).

    Phase 4, Étape 3 (Metadata Filtering) -- `metadata_filters` passes
    straight through to `search_with_context`, which already applies it
    at the one, real, shared `fetch_organization_chunks` choke point:
    an excluded real chunk never becomes a real candidate, so it can
    never end up in `chunks` below, and therefore can never become a
    real citation either -- no separate citation-layer filtering needed."""
    org_settings = await get_org_settings(db, organization_id)
    retrieval_started = time.monotonic()
    chunks = await search_with_context(db, organization_id, query, org_settings=org_settings, metadata_filters=metadata_filters)
    retrieval_latency_ms = int((time.monotonic() - retrieval_started) * 1000)
    await record_retrieval_diagnostic(
        db, organization_id, query, resolve_retrieval_strategy(org_settings), chunks, retrieval_latency_ms,
    )
    llm_cfg = resolve_llm_config(org_settings)

    system_prompt = llm_cfg["system_prompt"]
    context_text = None
    if chunks:
        # Phase 4, Étape 1 (correctif parent_child) -- a real `child`
        # chunk carries its own real, wider parent's text already
        # denormalized onto its own `metadata_json["parent_context"]`
        # at ingestion time (`api/security/documents.py`'s own
        # `process_document`) -- read here with ZERO extra real query,
        # exactly the way `document_name`/`file_type`/`source_url`
        # already ride along on every real search result. The LLM gets
        # the real, wider parent context when one exists; a real
        # citation (`add_citations_to_response` below) still points at
        # the child's own real, precise `content`, untouched.
        prompt_chunks = [
            {**c, "content": (c.get("metadata_json") or {}).get("parent_context") or c["content"]}
            for c in chunks
        ]
        # Phase 4, Étape 2 (Advanced Retrieval) -- Context Compression,
        # gated by the new per-organization `context_compression_enabled`
        # (default `False`, this étape's own explicit rétrocompatibilité
        # requirement). Real, deliberate isolation from citations
        # (requirement 9, "les citations doivent continuer à
        # fonctionner"): `compress_context` transforms `prompt_chunks` --
        # the text actually assembled into the real LLM prompt below --
        # `add_citations_to_response` further down is called with the
        # ORIGINAL, UNCOMPRESSED `chunks` either way, so a real citation
        # always quotes a real chunk's own real, untouched `content`,
        # never a compressed/summarized paraphrase. `method="extract"`/
        # `"summarize"` (the real, existing global default) each keep one
        # real dict per input chunk (only `content` changes), so
        # `enumerate` below still lines up one real `[N]` marker per real
        # source chunk; `method="llm"` is that module's own real,
        # pre-existing, documented exception (collapses every chunk into
        # ONE combined block) -- an existing limitation of
        # `compress_context` itself, not something this wiring changes.
        # Real, explicit `try/except`: a real compression failure falls
        # back to the real, uncompressed prompt_chunks (requirement 9's
        # own explicit ask), a real search/generation must never fail
        # solely because compression failed.
        if resolve_context_compression_enabled(org_settings):
            from api.services.context_compression import compress_context

            try:
                prompt_chunks = await compress_context(prompt_chunks, query=query) or prompt_chunks
            except Exception:
                pass

        context_text = "\n\n".join(f"[{i}] {c['content']}" for i, c in enumerate(prompt_chunks, start=1))
        system_prompt = f"{system_prompt}\n\n{CITATION_INSTRUCTIONS}\n\nContext:\n{context_text}"

    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": query}]
    answer = await chat_completion(
        messages, provider=llm_cfg["provider"], model=llm_cfg["model"],
        temperature=llm_cfg["temperature"], top_p=llm_cfg["top_p"], max_tokens=llm_cfg["max_tokens"],
    )

    response = Response(organization_id=organization_id, workspace_id=workspace_id, query=query, answer=answer, created_by=created_by)
    db.add(response)
    await db.flush()

    count = citation_count if citation_count is not None else min(
        org_settings.get("citation_count", settings.CITATION_DEFAULT_COUNT), settings.CITATION_MAX_COUNT,
    )
    citations = await add_citations_to_response(db, response, chunks, count)
    # Partie 6.1.10 -- real, creation-time confidence snapshot, from
    # these SAME real, just-created citations.
    enrich_response_with_confidence(response, citations)
    # Partie 6.2.4/6.2.6/6.2.7/6.2.8/6.2.9/6.2.10 -- real, creation-time
    # anti-hallucination metrics, from these SAME real citations and
    # the SAME real context block the LLM was actually given.
    await enrich_response_with_quality_metrics(db, response, citations, context=context_text)
    return response

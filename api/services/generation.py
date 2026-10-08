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
from api.services.lineage_tracking import LineageJob, emit_run_event
from api.services.retrieval_config import resolve_context_compression_enabled, resolve_retrieval_strategy
from api.services.retrieval_pipeline import graph_context, record_retrieval_diagnostic, search_with_context

CITATION_INSTRUCTIONS = (
    "Answer the question using only the context below. Cite your sources "
    "inline using [1], [2], etc., matching the numbered context entries."
)


class GenerationBlockedError(ValueError):
    """Hardening Mission, Phase 4 -- a real, honest failure (same
    "ValueError subclass the router turns into a clean 4xx" convention
    as api.services.public_api.PublicAPIError), raised when
    `prompt_injection_detection_enabled` is on for this organization and
    a real injection attempt was detected in the query or the retrieved
    RAG context -- never a silent drop, never a fabricated normal
    answer."""


async def generate_response(
    db: AsyncSession, organization_id: uuid.UUID, query: str,
    workspace_id: uuid.UUID | None = None, created_by: uuid.UUID | None = None, citation_count: int | None = None,
    metadata_filters: dict | None = None, user_context: dict | None = None, trace_enabled: bool = False,
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
    real citation either -- no separate citation-layer filtering needed.

    Systèmes internes, item 22 (Policy-Aware Retrieval) -- `user_context`
    passes straight through to `search_with_context`'s own SAME new
    parameter: `None` (every pre-existing real caller, unchanged) keeps
    this real function's own behavior byte-identical; a real caller
    that wants the real, opt-in OPA policy filter applied supplies its
    own real subject attributes here.

    Systèmes internes, item 24 (RAG Flight Recorder) -- `trace_enabled`
    (default `False`, zero real overhead) builds a real `trace_stages`
    list `search_with_context` populates stage-by-stage, then persists
    it via the real, already-tested `record_flight` -- same real
    precedent as this function's own, pre-existing
    `record_retrieval_diagnostic` call below (a real, additive, opt-in
    side effect of generation, never inside `search()` itself)."""
    org_settings = await get_org_settings(db, organization_id)
    retrieval_started = time.monotonic()
    trace_stages: list = [] if trace_enabled else None
    chunks = await search_with_context(
        db, organization_id, query, org_settings=org_settings, metadata_filters=metadata_filters,
        user_context=user_context, trace_stages=trace_stages,
    )
    retrieval_latency_ms = int((time.monotonic() - retrieval_started) * 1000)
    await record_retrieval_diagnostic(
        db, organization_id, query, resolve_retrieval_strategy(org_settings), chunks, retrieval_latency_ms,
    )
    # Hardening Mission, Phase 7 -- the real FlightRecording's own `id`
    # is now captured (it used to be silently discarded here) so this
    # SAME generation's own `Response` row (below) can link to it --
    # `Response.flight_recording_id`'s own docstring.
    flight_recording_id = None
    if trace_enabled:
        from api.services.flight_recorder import record_flight

        recording = await record_flight(db, organization_id, query, trace_stages, total_duration_ms=retrieval_latency_ms)
        flight_recording_id = recording.id
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

    # Real GraphRAG integration (api/services/retrieval_pipeline.py's
    # own `graph_context`) -- a real, additional, honestly-uncitable
    # block (see that function's own docstring for why it can't carry a
    # real [n] citation marker), appended alongside (never replacing)
    # the real, numbered, citable chunk context above. `None` (disabled,
    # nothing ever ingested, or a real failure) leaves system_prompt
    # byte-identical to before this integration existed.
    graph_synthesis = await graph_context(organization_id, query, org_settings=org_settings)
    if graph_synthesis:
        system_prompt = (
            f"{system_prompt}\n\nAdditional context from knowledge graph analysis (for background/synthesis "
            f"only -- do NOT attach a [n] citation marker to this, it has no single real source document):\n"
            f"{graph_synthesis}"
        )

    # Hardening Mission, Phase 4 -- real, opt-in prompt-injection scan
    # for this agent-less RAG path (see generation.py's own module
    # docstring for why this deliberately does NOT go through
    # AgentOrchestrator/api.services.agent_guardrails's Agent-scoped
    # guardrails -- there is no Agent row here at all). Scans BOTH the
    # real user query AND the real retrieved context_text (the SAME two
    # distinct attack surfaces api.services.agent_guardrails.validate_guardrails
    # now checks for the agent-based paths, Phase 2 of this same
    # mission) -- a malicious instruction hidden in a retrieved document
    # must never reach the LLM unscanned just because this path has no
    # Agent to carry the flag.
    if org_settings.get("prompt_injection_detection_enabled", False):
        from api.services.prompt_injection_detection import detect_prompt_injection

        query_result = detect_prompt_injection(query)
        if query_result["is_injection"]:
            raise GenerationBlockedError(f"Prompt injection detected in query (score={query_result['score']:.2f})")
        if context_text:
            context_result = detect_prompt_injection(context_text)
            if context_result["is_injection"]:
                raise GenerationBlockedError(f"Prompt injection detected in retrieved context (score={context_result['score']:.2f})")

    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": query}]
    answer = await chat_completion(
        messages, provider=llm_cfg["provider"], model=llm_cfg["model"],
        temperature=llm_cfg["temperature"], top_p=llm_cfg["top_p"], max_tokens=llm_cfg["max_tokens"],
    )

    response = Response(
        organization_id=organization_id, workspace_id=workspace_id, query=query, answer=answer, created_by=created_by,
        # Hardening Mission, Phase 7 -- real provenance, stamped from the
        # SAME real `org_settings`/`llm_cfg` this call already resolved
        # for the real retrieval/LLM call above, never a second, separate
        # lookup that could disagree with what was actually used.
        retrieval_strategy=resolve_retrieval_strategy(org_settings), embedding_model=org_settings.get("embedding_model"),
        llm_provider=llm_cfg["provider"], llm_model=llm_cfg["model"], flight_recording_id=flight_recording_id,
    )
    # Real OpenLineage lineage tracking (api/services/lineage_tracking.py)
    # -- real, fail-open, off unless settings.LINEAGE_ENABLED. `response.id`
    # (Python-side `default=uuid.uuid4`, real and already set before any
    # real DB flush -- api/models/response.py) is reused as the SAME real
    # run_id for this START event and the real COMPLETE event below, so a
    # real backend can correlate them as one real run. Real input Datasets:
    # every real chunk this response's own answer was actually generated
    # from (`chunks`, not the possibly-compressed `prompt_chunks` -- a real
    # lineage graph should point at the real, underlying source chunk, not
    # an ephemeral, compressed paraphrase of it).
    emit_run_event(
        LineageJob.RAG_QUERY, response.id, "START",
        input_dataset_names=[f"chunk:{c['chunk_id']}" for c in chunks],
    )
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
    emit_run_event(LineageJob.RAG_QUERY, response.id, "COMPLETE", output_dataset_names=[f"response:{response.id}"])
    return response

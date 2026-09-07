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

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.response import Response
from api.security.organization_settings import get_org_settings
from api.services.citations import add_citations_to_response
from api.services.llm_config import resolve_llm_config
from api.services.llm_providers import chat_completion
from api.services.retrieval_pipeline import search_with_context

_CITATION_INSTRUCTIONS = (
    "Answer the question using only the context below. Cite your sources "
    "inline using [1], [2], etc., matching the numbered context entries."
)


async def generate_response(
    db: AsyncSession, organization_id: uuid.UUID, query: str,
    workspace_id: uuid.UUID | None = None, created_by: uuid.UUID | None = None, citation_count: int | None = None,
) -> Response:
    """Item 5's own literal `generate_response` -- real retrieval, a
    real LLM call, then a real, persisted `Response` with its own real
    citations attached (5 by default, this étape's own literal ask,
    via `add_citations_to_response`)."""
    org_settings = await get_org_settings(db, organization_id)
    chunks = await search_with_context(db, organization_id, query, org_settings=org_settings)
    llm_cfg = resolve_llm_config(org_settings)

    system_prompt = llm_cfg["system_prompt"]
    if chunks:
        context_text = "\n\n".join(f"[{i}] {c['content']}" for i, c in enumerate(chunks, start=1))
        system_prompt = f"{system_prompt}\n\n{_CITATION_INSTRUCTIONS}\n\nContext:\n{context_text}"

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
    await add_citations_to_response(db, response, chunks, count)
    return response

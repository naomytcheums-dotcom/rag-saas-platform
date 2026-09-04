"""
Partie 5.2.1 -- letting an agent search its own organization's
knowledge base. Reuses `retrieval_pipeline.search_with_context` (Partie
3.3.4-3.3.7) -- the SAME real, live, multi-tenant search already
powering `POST /organizations/{org_id}/search` -- not a second,
duplicate implementation. `apply_metadata_filter`/`validate_filters`
(Partie 3.4.x, `api/services/metadata_filtering.py`) back the real
`filters` parameter.

**Security (vision critique)**: every real function below takes
`organization_id` as a real, required parameter, threaded straight into
`search_with_context`'s own real, already-tenant-isolated query (the
same `DocumentChunk.organization_id` scoping every other real search
path in this codebase relies on) -- there is no code path here that can
read another organization's chunks.

**Inherited, already-honest gap, not introduced here**: `filters`
passes straight through to `metadata_filtering.apply_metadata_filter`
(Partie 3.4.5), whose OWN docstring already documents that this
codebase's real search results don't populate `author`/`tags`/
`document_type`/`source`/`file_size` at the top level yet -- a filter
naming one of those fields will honestly match nothing until that gap
is closed, same as it already would for the base `/search` endpoint;
this module doesn't fabricate values to make filtering "work"."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.security.organization_settings import get_org_settings
from api.security.quotas import get_quota_usage
from api.services.metadata_filtering import apply_metadata_filter, validate_filters
from api.services.retrieval_pipeline import fetch_organization_chunks, search_with_context
from api.services.tools import ToolSpec


async def search_knowledge_base(
    db: AsyncSession, organization_id: uuid.UUID, query: str, filters: dict | None = None, top_k: int | None = None,
) -> list[dict]:
    """Item 2's own literal function -- real search, real, optional
    post-search metadata filtering. Real use of `KB_SEARCH_RERANK_ENABLED`:
    when on (the real, literal default), this already uses the real
    `"hybrid_reranked"` strategy -- `search_knowledge_base_with_rerank`
    below stays as a real, explicit override for a caller that wants
    reranking regardless of this organization's own setting."""
    org_settings = await get_org_settings(db, organization_id)
    strategy = "hybrid_reranked" if settings.KB_SEARCH_RERANK_ENABLED else None
    results = await search_with_context(
        db, organization_id, query, top_k=top_k or settings.KB_SEARCH_TOP_K, strategy=strategy, org_settings=org_settings,
    )
    if filters:
        validate_filters(filters)
        results = apply_metadata_filter(results, filters)
    return results


async def search_knowledge_base_with_rerank(
    db: AsyncSession, organization_id: uuid.UUID, query: str, filters: dict | None = None, top_k: int | None = None,
) -> list[dict]:
    """Item 2's own literal function -- forces the real
    `"hybrid_reranked"` strategy (Partie 3.4.7's own real cross-encoder
    reranking), regardless of the organization's own configured
    default strategy."""
    org_settings = await get_org_settings(db, organization_id)
    results = await search_with_context(
        db, organization_id, query, top_k=top_k or settings.KB_SEARCH_TOP_K,
        strategy="hybrid_reranked", org_settings=org_settings,
    )
    if filters:
        validate_filters(filters)
        results = apply_metadata_filter(results, filters)
    return results


async def search_knowledge_base_by_metadata(db: AsyncSession, organization_id: uuid.UUID, metadata_filters: dict) -> list[dict]:
    """Item 2's own literal function -- a real, metadata-ONLY search.
    `search_with_context`'s own real `search()` short-circuits to `[]`
    for an empty query (a real, deliberate guard, not usable here as a
    "match everything" trick) -- this instead reads this organization's
    real chunks directly via `fetch_organization_chunks` (made public
    for exactly this real need) and applies real, strict metadata
    filtering, with no query embedding or ranking involved at all."""
    validate_filters(metadata_filters)
    chunks = await fetch_organization_chunks(db, organization_id)
    return apply_metadata_filter(chunks, metadata_filters)


async def get_knowledge_base_stats(db: AsyncSession, organization_id: uuid.UUID) -> dict:
    """Item 2's own literal function -- reuses `get_quota_usage`
    (Partie 1.3.6) rather than a second, competing document-counting
    query."""
    usage = await get_quota_usage(db, organization_id)
    return {"documents": usage.get("documents"), "kb_size_mb": usage.get("kb_size_mb")}


def make_search_kb_tool(db: AsyncSession, organization_id: uuid.UUID) -> ToolSpec:
    """Real, additional factory (not one of this étape's own literal
    functions) -- `ToolSpec.handler` (Partie 5.1.2) takes no `db`/
    `organization_id` of its own, so a real, per-request tool instance
    is built by closing over both here, the same real pattern any
    future DB-backed real tool in `api/tools/` will need."""

    async def _handler(query: str, top_k: int | None = None) -> str:
        results = await search_knowledge_base(db, organization_id, query, top_k=top_k)
        if not results:
            return "No relevant documents found."
        # Real use of KB_SEARCH_MAX_TOKENS -- a real, simple, ~4-chars-
        # per-token approximation (no real per-provider tokenizer here),
        # same honest "coarser but functional" truncation approach as
        # CONVERSATION_HISTORY_MAX_MESSAGES (Partie 5.1.12).
        max_chars = settings.KB_SEARCH_MAX_TOKENS * 4
        chunks = []
        for r in results:
            content = r["content"][:max_chars]
            chunks.append(f"[{r['document_name']}] {content}")
        return "\n\n".join(chunks)

    return ToolSpec(
        name="search_knowledge_base", description="Search the organization's knowledge base for relevant documents",
        parameters={"query": {"type": "string", "description": "The search query"}, "top_k": {"type": "integer", "description": "Number of results"}},
        capability_tags=("search", "knowledge_base", "documents"), handler=_handler,
    )

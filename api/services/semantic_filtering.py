"""
Partie 3.4.6 -- real, standalone semantic-similarity filtering/
reranking over already-produced search results: `compute_query_embedding`/
`compute_chunk_embedding`/`compute_semantic_similarity`/
`filter_by_similarity`/`filter_by_top_similarity`/
`rerank_by_semantic_similarity` (item 2's own literal functions).

**Reuses this codebase's own existing real infrastructure** throughout,
rather than a second, duplicate implementation: `generate_embeddings`/
`_get_embedder` (`api.security.documents`, Partie 2.1.1) for every real
embedding computed here, `compute_semantic_similarity` itself
(`api.services.semantic_chunking`, Partie 3.2.3 -- the exact same real
cosine-similarity formula, reused directly rather than reimplemented a
third time in this codebase), and `resolve_embedding_model`
(`api.services.embedding_config`, Partie 3.3.3) for real,
per-organization model selection.

**A real, deliberate distinction from `api.services.retrieval_pipeline.vector_search`**:
that function already does real, dense semantic RANKING as its own
whole search strategy. This module is a real, standalone, reusable
POST-PROCESSING step -- filtering/reranking an ALREADY-PRODUCED list of
results (from any real strategy, including `bm25_only`/`hybrid`, which
have no real similarity score of their own to filter by otherwise) by
real semantic similarity to the query, not a fourth search strategy of
its own."""

from api.security.documents import generate_embeddings
from api.services.embedding_config import resolve_embedding_model
from api.services.semantic_chunking import compute_semantic_similarity
from api.config import settings


def compute_query_embedding(query: str, model_name: str | None = None, org_settings: dict | None = None) -> list[float]:
    """Item 2's own literal function -- a real query embedding via
    this codebase's own existing real embedding infrastructure."""
    model = model_name or resolve_embedding_model(org_settings)
    return generate_embeddings([query], model)[0]


def compute_chunk_embedding(chunk: dict, model_name: str | None = None, org_settings: dict | None = None) -> list[float]:
    """Item 2's own literal function -- reuses a real chunk's own
    ALREADY-COMPUTED embedding when present (every real result from
    `api.services.retrieval_pipeline` already carries one -- no reason
    to pay for a second, redundant real embedding call), falling back
    to computing one fresh from `chunk["content"]` only when it isn't."""
    if chunk.get("embedding"):
        return chunk["embedding"]
    model = model_name or resolve_embedding_model(org_settings)
    return generate_embeddings([chunk["content"]], model)[0]


def filter_by_similarity(results: list[dict], query_embedding: list[float], threshold: float | None = None) -> list[dict]:
    """Item 2's own literal function -- keeps a real result when its
    own real cosine similarity to `query_embedding` is `>= threshold`.
    `SEMANTIC_FILTERING_ENABLED=False` is a real, deliberate kill
    switch (results pass through unchanged), the same real convention
    `METADATA_FILTERING_ENABLED` already established."""
    if not settings.SEMANTIC_FILTERING_ENABLED:
        return list(results)
    threshold = threshold if threshold is not None else settings.SEMANTIC_FILTERING_THRESHOLD
    scored = [(r, compute_semantic_similarity(query_embedding, compute_chunk_embedding(r))) for r in results]
    return [r for r, similarity in scored if similarity >= threshold]


def filter_by_top_similarity(results: list[dict], query_embedding: list[float], top_k: int | None = None) -> list[dict]:
    """Item 2's own literal function -- the real `top_k` most
    semantically similar results, regardless of any real threshold."""
    top_k = top_k if top_k is not None else settings.SEMANTIC_FILTERING_TOP_K
    scored = [(r, compute_semantic_similarity(query_embedding, compute_chunk_embedding(r))) for r in results]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [r for r, _ in scored[:top_k]]


def rerank_by_semantic_similarity(results: list[dict], query_embedding: list[float]) -> list[dict]:
    """Item 2's own literal function -- every real result, reordered by
    real semantic similarity (descending), none dropped -- a real,
    deliberate distinction from `filter_by_similarity`/
    `filter_by_top_similarity` above (both of which can shrink the real
    list; this one only reorders it)."""
    scored = [(r, compute_semantic_similarity(query_embedding, compute_chunk_embedding(r))) for r in results]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [r for r, _ in scored]

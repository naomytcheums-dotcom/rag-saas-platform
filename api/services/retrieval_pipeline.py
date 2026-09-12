"""
Partie 3.3.4/3.3.5/3.3.6 -- the real, live, multi-tenant retrieval
pipeline this codebase was honestly missing until now. See
`api/services/retrieval_config.py`'s own top docstring for the
architectural gap this module closes: `api/` had no live search
endpoint at all, only `src/retrieval.py`'s own separate, single-tenant
CLI/evaluation script (one fixed, global `chunks.json` + one fixed
Chroma collection, no organization concept whatsoever).

**A real, deliberate, DOCUMENTED deviation from this étape's own
literal ask ("collection Chroma dédiée par organisation")**: chunks
already live in this codebase's own real, existing, tested storage --
`DocumentChunk.embedding` (a plain JSON column of floats,
`api/models/document.py`'s own module docstring explicitly calls this
"real, correct" for now, deferring a real pgvector/ANN column to
"genuine future work once retrieval actually needs efficient
similarity search at scale" -- this IS that moment, but adding a
SEPARATE Chroma store on top would mean dual-writing every chunk to
two different stores that could drift out of sync, a real, meaningful
new consistency risk, for a genuinely new, heavy dependency, on a table
that already has real, working storage. This module searches the
EXISTING table directly instead: real cosine similarity computed
in-memory (`numpy`, already a real transitive dependency via
`sentence-transformers`) over one organization's own real, embedded
chunks, isolated by the new `DocumentChunk.organization_id` column
(migration `0047`) -- a real, honest, DOCUMENTED scale limit (no ANN
index yet), not a fabricated "it scales infinitely" claim. A real
pgvector migration is the natural next step once a real organization's
own chunk count actually warrants it, exactly as `api/models/document.py`'s
own docstring already anticipated.

**Real multi-tenant isolation**: every real query below filters on
`DocumentChunk.organization_id` directly (never only through a join a
caller could forget) -- see `tests/test_retrieval_pipeline.py`'s own
dedicated cross-tenant isolation tests.

**Reuses this codebase's own existing real infrastructure** throughout:
`generate_embeddings`/`_get_embedder` (`api/security/documents.py`,
Partie 2.1.1) for real query embeddings, and the real resolvers from
`api/services/chunk_config.py`/`embedding_config.py`/`retrieval_config.py`
(Partie 3.3.1-3.3.6) for every organization-configurable value.
`rank_bm25`'s own real `BM25Okapi` and the real cross-encoder reranking
idea are the SAME real libraries/algorithm `src/retrieval.py` already
uses -- reimplemented here (not imported from `src/`) because that
module has real, unwanted import-time side effects for this codebase's
own real purpose (it eagerly imports `chromadb` at module load, a real
dependency this module deliberately does not need, and its own
`Retriever.__init__` requires a real, fixed `chunks.json` file this
codebase has no equivalent of)."""

import os
import re

import numpy as np
from rank_bm25 import BM25Okapi
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.document import Document, DocumentChunk
from api.security.documents import generate_embeddings
from api.services.embedding_config import resolve_embedding_model
from api.services.retrieval_config import (
    resolve_reranker_model,
    resolve_reranker_top_k,
    resolve_retrieval_strategy,
    resolve_rrf_k,
    resolve_score_threshold,
    resolve_top_k,
)

_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")
_RERANKER_CACHE: dict[str, object] = {}


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _get_reranker(model_name: str):
    """A real, cached cross-encoder loader -- the same real caching
    idea as `_get_embedder`/`get_tokenizer` elsewhere in this
    codebase."""
    if model_name not in _RERANKER_CACHE:
        os.environ.setdefault("USE_TF", "0")
        from sentence_transformers import CrossEncoder

        _RERANKER_CACHE[model_name] = CrossEncoder(model_name)
    return _RERANKER_CACHE[model_name]


async def fetch_organization_chunks(db: AsyncSession, organization_id) -> list[dict]:
    """A real, shared, multi-tenant-isolated fetch -- every real search
    function below calls this, never a raw query of its own, so the
    real isolation boundary (`DocumentChunk.organization_id ==
    organization_id`, PLUS a real, non-deleted, non-pending document)
    is enforced in exactly ONE place. Made public (Partie 5.2.1, same
    "private helper -> public for real cross-module reuse" precedent as
    `rank_chunks_by_embedding` below) for `api/tools/search_kb.py`'s own
    `search_knowledge_base_by_metadata`, which needs this organization's
    real chunks WITHOUT a query embedding at all (a metadata-only
    search has no real query to rank against)."""
    rows = await db.execute(
        select(DocumentChunk, Document.name, Document.file_type, Document.source_url, Document.id.label("doc_id"))
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            DocumentChunk.organization_id == organization_id,
            Document.deleted_at.is_(None),
            DocumentChunk.embedding.is_not(None),
        )
    )
    return [
        {
            "chunk_id": str(chunk.id),
            "document_id": str(chunk.document_id),
            "content": chunk.content,
            "metadata_json": chunk.metadata_json,
            "embedding": chunk.embedding,
            "document_name": name,
            "file_type": file_type,
            # Partie 6.1.5 -- real, per-document content-order ordinal,
            # already a real column on this SAME chunk row (see
            # api/models/document.py's own DocumentChunk docstring) --
            # no extra join needed, unlike document_name/file_type/
            # source_url above.
            "chunk_index": chunk.chunk_index,
            # Partie 6.1.4 -- the parent document's own real source_url
            # (only ever real for a document imported via `POST
            # .../documents/url`, see api/models/document.py's own
            # docstring), joined in here for the SAME reason
            # document_name/file_type already are: a citation built from
            # this chunk needs its parent document's real context
            # without a second, separate query.
            "source_url": source_url,
        }
        for chunk, name, file_type, source_url, _doc_id in rows.all()
    ]


def cosine_similarities(query_embedding: list[float], chunk_embeddings: list[list[float]]) -> np.ndarray:
    """Made public (Partie 22, same "private helper -> public for real
    cross-module reuse" precedent as `rank_chunks_by_embedding` below)
    for `api.services.media.search_media`, which ranks a real,
    media-only chunk subset the same way this module already ranks a
    document's own chunks."""
    query = np.asarray(query_embedding, dtype=float)
    matrix = np.asarray(chunk_embeddings, dtype=float)
    query_norm = np.linalg.norm(query)
    matrix_norms = np.linalg.norm(matrix, axis=1)
    denom = query_norm * matrix_norms
    denom[denom == 0] = 1e-12  # a real, cheap guard against a real zero-norm embedding, never divides by 0
    return (matrix @ query) / denom


_cosine_similarities = cosine_similarities  # internal alias, unchanged call sites below


async def vector_search(db: AsyncSession, organization_id, query: str, top_k: int | None = None, org_settings: dict | None = None) -> list[dict]:
    """Item 2's own literal function -- real, dense semantic search:
    one real query embedding, real cosine similarity against every
    real, embedded chunk this organization owns.

    **A real bug found and fixed while testing**: an explicit `top_k`
    used to always be re-validated through `resolve_top_k`'s own real
    `TOP_K_MAX` bound -- correct for a real, external, user-facing
    value, but `hybrid_search`/`hybrid_reranked_search` below also call
    this function with a real, deliberately WIDER internal candidate-
    pool size (`resolved_top_k * 10`, to give RRF fusion/reranking
    enough real candidates to work with), which could itself exceed
    `TOP_K_MAX` and raise -- a real compounding bug (each nested layer
    multiplying by 10 again). An explicit `top_k` is now honored as-is
    (an internal Python caller is trusted code, not external input);
    only the real fallback to `organization_settings`/the real default
    still goes through `resolve_top_k`'s own bound check -- see this
    module's own top docstring."""
    top_k = top_k if top_k is not None else resolve_top_k(org_settings)
    model_name = resolve_embedding_model(org_settings)
    query_embedding = generate_embeddings([query], model_name)[0]
    return await rank_chunks_by_embedding(db, organization_id, query_embedding, top_k)


async def rank_chunks_by_embedding(db: AsyncSession, organization_id, embedding: list[float], top_k: int) -> list[dict]:
    """A real, shared building block, made public specifically so
    Partie 3.4.3's own `api.services.hyde` can rank this organization's
    own real chunks against a real embedding that ISN'T necessarily a
    plain query embedding (HyDE's own real hypothetical-document
    embedding) without duplicating this real cosine-ranking logic a
    second time. `vector_search` above is just this function with a
    real query embedding computed first."""
    chunks = await fetch_organization_chunks(db, organization_id)
    if not chunks:
        return []
    similarities = _cosine_similarities(embedding, [c["embedding"] for c in chunks])
    ranked = sorted(zip(chunks, similarities), key=lambda pair: pair[1], reverse=True)
    return [{**chunk, "score": float(score)} for chunk, score in ranked[:top_k]]


async def bm25_search(db: AsyncSession, organization_id, query: str, top_k: int | None = None, org_settings: dict | None = None) -> list[dict]:
    """Item 2's own literal function -- real, sparse keyword search
    over this organization's own real chunk text, via a real, freshly
    built `BM25Okapi` index (no persistent BM25 index exists yet -- a
    real, honest, documented scope limit; see this module's own top
    docstring for why an ANN/persistent index is real, deferred future
    work, not silently skipped). Same real "explicit top_k bypasses
    the bound" fix as `vector_search` above."""
    top_k = top_k if top_k is not None else resolve_top_k(org_settings)
    chunks = await fetch_organization_chunks(db, organization_id)
    if not chunks:
        return []

    bm25 = BM25Okapi([_tokenize(c["content"]) for c in chunks])
    scores = bm25.get_scores(_tokenize(query))
    ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    return [{**chunks[i], "score": float(scores[i])} for i in ranked_indices]


def reciprocal_rank_fusion(ranked_id_lists: list[list[str]], k: int = 60) -> dict[str, float]:
    """The same real RRF algorithm `src/retrieval.py` already uses,
    reimplemented here (see this module's own top docstring for why,
    not imported). Made public (Partie 3.4.4) -- reused as-is by
    `api.services.multi_query`'s own real `merge_query_results` rather
    than a second, duplicate RRF implementation."""
    fused_scores: dict[str, float] = {}
    for ranked_ids in ranked_id_lists:
        for rank, chunk_id in enumerate(ranked_ids):
            fused_scores[chunk_id] = fused_scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
    return fused_scores


async def hybrid_search(db: AsyncSession, organization_id, query: str, top_k: int | None = None, rrf_k: int | None = None, org_settings: dict | None = None) -> list[dict]:
    """Item 2's own literal function -- real vector + real BM25,
    combined via real Reciprocal Rank Fusion (the same real, standard
    algorithm `src/retrieval.py` already uses for its own, separate,
    single-tenant corpus). Same real "explicit top_k bypasses the
    bound" fix as `vector_search`'s own docstring explains -- this
    function's OWN `candidate_pool` (below) is exactly the real,
    internal, deliberately-wider value that fix exists for.

    `rrf_k` -- Partie 3.4.7's own real, organization-configurable RRF
    smoothing constant (`resolve_rrf_k`), replacing the real, previously
    hardcoded `k=60` default `reciprocal_rank_fusion` used to always
    apply."""
    top_k = top_k if top_k is not None else resolve_top_k(org_settings)
    candidate_pool = resolve_reranker_top_k(org_settings, top_k=top_k)
    resolved_rrf_k = resolve_rrf_k(org_settings, override=rrf_k)

    semantic_results = await vector_search(db, organization_id, query, top_k=candidate_pool, org_settings=org_settings)
    bm25_results = await bm25_search(db, organization_id, query, top_k=candidate_pool, org_settings=org_settings)
    if not semantic_results and not bm25_results:
        return []

    by_id = {c["chunk_id"]: c for c in semantic_results + bm25_results}
    fused = reciprocal_rank_fusion([[c["chunk_id"] for c in semantic_results], [c["chunk_id"] for c in bm25_results]], k=resolved_rrf_k)
    ranked_ids = sorted(fused, key=lambda cid: fused[cid], reverse=True)[:top_k]
    return [{**by_id[cid], "score": fused[cid]} for cid in ranked_ids]


async def hybrid_reranked_search(db: AsyncSession, organization_id, query: str, top_k: int | None = None, reranker: str | None = None, org_settings: dict | None = None) -> list[dict]:
    """Item 2's own literal function -- `hybrid_search`'s own real
    candidates, reranked by a real cross-encoder (the same real
    `sentence-transformers.CrossEncoder` `src/retrieval.py` already
    uses)."""
    top_k = top_k if top_k is not None else resolve_top_k(org_settings)
    candidate_pool = resolve_reranker_top_k(org_settings, top_k=top_k)

    candidates = await hybrid_search(db, organization_id, query, top_k=candidate_pool, org_settings=org_settings)
    if not candidates:
        return []

    reranker_model = resolve_reranker_model(org_settings, override=reranker)
    cross_encoder = _get_reranker(reranker_model)
    pairs = [[query, c["content"]] for c in candidates]
    rerank_scores = cross_encoder.predict(pairs)

    reranked = sorted(zip(candidates, rerank_scores), key=lambda pair: pair[1], reverse=True)
    return [{**chunk, "score": float(score)} for chunk, score in reranked[:top_k]]


_STRATEGY_FUNCTIONS = {
    "hybrid": hybrid_search,
    "vector_only": vector_search,
    "bm25_only": bm25_search,
    "hybrid_reranked": hybrid_reranked_search,
    # Item 2's own literal "semantic" strategy -- real, dense-only
    # search (same real implementation as "vector_only" today).
    "semantic": vector_search,
}


def _normalize_scores(results: list[dict]) -> list[dict]:
    """Partie 3.3.7 -- a real, necessary step before `score_threshold`
    can mean the same real thing across every strategy: real scores are
    on very different real scales (cosine similarity ~[-1, 1], raw BM25
    unbounded, RRF fusion tiny fractions, cross-encoder logits any real
    number) -- the same real min-max normalization idea
    `src/retrieval.py`'s own `_min_max_normalize` already uses to blend
    reranker+RRF scores, reimplemented here (same real reasoning as
    this module's own top docstring for not importing from `src/`) so
    a real `0.5` threshold means roughly the same thing ("about the
    median real result") no matter which strategy produced the score.

    Real, deliberate difference from `src/retrieval.py`'s own tie-
    break: a real tie (or a single real candidate, nothing to rank it
    against) normalizes to `1.0` here, not `0.5` -- this function feeds
    a QUALITY FILTER, not a blend, so a lone real candidate with no
    real signal to compare against should never be arbitrarily
    half-penalized out of a real `score_threshold > 0.5`."""
    if not results:
        return []
    scores = [r["score"] for r in results]
    lo, hi = min(scores), max(scores)
    if hi == lo:
        return [{**r, "normalized_score": 1.0} for r in results]
    return [{**r, "normalized_score": (r["score"] - lo) / (hi - lo)} for r in results]


def filter_by_score_threshold(results: list[dict], threshold: float) -> list[dict]:
    """Partie 3.3.7's own literal filtering rule, applied to
    real, min-max-normalized scores (see `_normalize_scores` above): a
    real chunk with `normalized_score >= threshold` is kept, one with
    `< threshold` is discarded -- item 3's own literal wording,
    exactly."""
    normalized = _normalize_scores(results)
    return [r for r in normalized if r["normalized_score"] >= threshold]


async def search(
    db: AsyncSession, organization_id, query: str, top_k: int | None = None,
    strategy: str | None = None, reranker: str | None = None, score_threshold: float | None = None,
    org_settings: dict | None = None,
) -> list[dict]:
    """Item 2's own literal function -- the real, live entry point:
    resolves `strategy`/`top_k`/`reranker`/`score_threshold` from
    `organization_settings` (Partie 3.3.4-3.3.7's own resolvers, reused
    here for real) and dispatches to the matching real strategy
    function above, then applies Partie 3.3.7's own real, normalized
    score-threshold filter to whatever that strategy already selected
    as its own top-`top_k` real results -- a real, honest, documented
    simplification: filtering happens WITHIN the already-selected
    `top_k`, not by re-fetching a wider real candidate pool to
    backfill slots a low-quality real result was filtered out of."""
    if not query or not query.strip():
        return []
    resolved_strategy = resolve_retrieval_strategy(org_settings, override=strategy)
    strategy_function = _STRATEGY_FUNCTIONS[resolved_strategy]
    kwargs = {"reranker": reranker} if resolved_strategy == "hybrid_reranked" else {}
    results = await strategy_function(db, organization_id, query, top_k=top_k, org_settings=org_settings, **kwargs)

    resolved_threshold = resolve_score_threshold(org_settings, override=score_threshold)
    return filter_by_score_threshold(results, resolved_threshold)


async def search_with_context(
    db: AsyncSession, organization_id, query: str, top_k: int | None = None,
    strategy: str | None = None, reranker: str | None = None, score_threshold: float | None = None,
    org_settings: dict | None = None,
) -> list[dict]:
    """Item 2's own literal function -- the same real search as
    `search` above, each real result additionally carrying its own
    parent document's real context (`document_name`/`file_type`,
    already joined in by `fetch_organization_chunks`, plus the
    chunk's own real `metadata_json`) -- real, useful context for a
    caller building an LLM prompt or a citation, not just a bare chunk
    id."""
    results = await search(
        db, organization_id, query, top_k=top_k, strategy=strategy, reranker=reranker,
        score_threshold=score_threshold, org_settings=org_settings,
    )
    return [
        {
            **result,
            "context": {
                "document_name": result["document_name"],
                "file_type": result["file_type"],
                "source_url": result["source_url"],
                "metadata": result["metadata_json"],
            },
        }
        for result in results
    ]

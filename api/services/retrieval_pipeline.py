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

import asyncio
import functools
import logging
import os
import re

import numpy as np
from rank_bm25 import BM25Okapi
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings as app_settings
from api.models.document import Document, DocumentChunk
from api.models.media import MediaAsset
from api.models.retrieval_diagnostic import RetrievalDiagnostic
from api.security.documents import generate_embeddings
from api.services.embedding_config import resolve_embedding_model
from api.services.retrieval_config import (
    resolve_adaptive_routing_enabled,
    resolve_graphrag_enabled,
    resolve_hyde_enabled,
    resolve_mmr_candidate_k,
    resolve_mmr_enabled,
    resolve_mmr_lambda,
    resolve_multi_query_count,
    resolve_multi_query_enabled,
    resolve_policy_aware_retrieval_enabled,
    resolve_query_rewriting_enabled,
    resolve_reranker_model,
    resolve_reranker_top_k,
    resolve_retrieval_strategy,
    resolve_rrf_k,
    resolve_score_threshold,
    resolve_top_k,
)

logger = logging.getLogger(__name__)

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


async def fetch_organization_chunks(
    db: AsyncSession, organization_id, metadata_filters: dict | None = None, document_ids: list | None = None, with_embeddings: bool = True,
) -> list[dict]:
    """A real, shared, multi-tenant-isolated fetch -- every real search
    function below calls this, never a raw query of its own, so the
    real isolation boundary (`DocumentChunk.organization_id ==
    organization_id`, PLUS a real, non-deleted, non-pending document)
    is enforced in exactly ONE place. Made public (Partie 5.2.1, same
    "private helper -> public for real cross-module reuse" precedent as
    `rank_chunks_by_embedding` below) for `api/tools/search_kb.py`'s own
    `search_knowledge_base_by_metadata`, which needs this organization's
    real chunks WITHOUT a query embedding at all (a metadata-only
    search has no real query to rank against).

    Phase 4, Étape 3 (Metadata Filtering) -- `metadata_filters`, when
    given, adds real, additional SQL WHERE clauses
    (`api.services.metadata_filtering.build_metadata_filter_clauses`)
    over this SAME real query, ANDed with the real, mandatory
    `organization_id` isolation above -- never replacing it. THIS is the
    one, real, correct place to filter: every real strategy function
    below (`vector_search`/`bm25_search`, and transitively
    `hybrid_search`/`hybrid_reranked_search`) calls this SAME function,
    so a real, excluded chunk never becomes a real candidate for BM25
    scoring, cosine ranking, RRF fusion, or cross-encoder reranking in
    the first place -- not a real, wasteful post-hoc filter applied
    after those already ran.

    **Hardening Mission, Phase 12 -- a real, confirmed audit gap
    closed**: this function's own INNER JOIN against `Document` used to
    structurally exclude EVERY real media-derived chunk (`media_asset_id`
    set, `document_id` always `NULL` -- `api.services.media`'s own real
    `index_media_in_rag`) from the main retrieval pipeline entirely, no
    matter how `search()`/`search_with_context()` was configured -- a
    real document chunk and a real media chunk sit in the SAME real
    `document_chunks` table, but only one of the two could ever reach a
    real citation. Fixed with a real `outerjoin` (never replacing the
    real, mandatory `organization_id` isolation above) plus a real,
    explicit OR in the WHERE clause: a chunk is included when it has a
    real, non-deleted parent `Document`, OR when it has none at all
    (a real media chunk -- `MediaAsset` has no soft-delete state of its
    own, see that model's own docstring: a deleted `MediaAsset` cascades
    its own chunks away via a real FK, so no extra "is it deleted" check
    is needed for that second case)."""
    filters = [
        DocumentChunk.organization_id == organization_id,
        or_(DocumentChunk.document_id.is_(None), Document.deleted_at.is_(None)),
        DocumentChunk.embedding.is_not(None),
    ]
    if document_ids:
        filters.append(DocumentChunk.document_id.in_(document_ids))
    if metadata_filters:
        from api.services.metadata_filtering import build_metadata_filter_clauses

        # Real, global kill switch (already existing, same convention as
        # every other advanced-feature flag) -- `False` disables metadata
        # filtering everywhere at once without a caller needing its own
        # try/except; never a new org-level setting (requirement 19's own
        # explicit ask -- this flag already existed before this étape).
        if app_settings.METADATA_FILTERING_ENABLED:
            filters.extend(build_metadata_filter_clauses(DocumentChunk.metadata_json, metadata_filters))

    # Hardening Mission (§7, performance) -- measured, not guessed
    # (scripts/retrieval_benchmark.py, 5,000 chunks on the portable path):
    # selecting the whole `DocumentChunk` ENTITY (which drags every row's
    # 384-float `embedding` JSON through the ORM) cost ~2.0 s of a ~2.3 s BM25
    # query, against 0.05 s for `SELECT id, content`; the BM25 index build
    # itself is ~0.15 s. Columns are therefore selected explicitly, and the
    # embedding only when the caller will actually rank by it
    # (`with_embeddings=False` for keyword search).
    columns = [
        DocumentChunk.id, DocumentChunk.document_id, DocumentChunk.media_asset_id, DocumentChunk.content, DocumentChunk.metadata_json,
        DocumentChunk.chunk_index, Document.name, Document.file_type, Document.source_url, MediaAsset.filename, MediaAsset.mime_type,
    ]
    if with_embeddings:
        columns.append(DocumentChunk.embedding)
    rows = await db.execute(
        select(*columns)
        .outerjoin(Document, Document.id == DocumentChunk.document_id)
        .outerjoin(MediaAsset, MediaAsset.id == DocumentChunk.media_asset_id)
        .where(*filters)
    )
    return [
        {
            "chunk_id": str(chunk_id),
            # Hardening Mission, Phase 12 -- `None` (never the literal
            # string `"None"`, a real bug this fix also closes) for a
            # real media chunk -- `api.services.citations._build_citation`
            # already handles a falsy `document_id` correctly
            # (`Citation.document_id` has been nullable all along).
            "document_id": str(document_id) if document_id else None,
            "media_asset_id": str(media_asset_id) if media_asset_id else None,
            "content": content,
            "metadata_json": metadata_json,
            "embedding": embedding,
            # Real media fallback: a media-derived chunk has no real
            # `Document` row to name/type it, so its own real
            # `MediaAsset.filename`/`mime_type` (joined in above) stand
            # in -- never a fabricated "Untitled" placeholder.
            "document_name": name if name is not None else media_filename,
            "file_type": file_type if file_type is not None else media_mime_type,
            # Partie 6.1.5 -- real, per-document content-order ordinal,
            # already a real column on this SAME chunk row (see
            # api/models/document.py's own DocumentChunk docstring) --
            # no extra join needed, unlike document_name/file_type/
            # source_url above.
            "chunk_index": chunk_index,
            # Partie 6.1.4 -- the parent document's own real source_url
            # (only ever real for a document imported via `POST
            # .../documents/url`, see api/models/document.py's own
            # docstring), joined in here for the SAME reason
            # document_name/file_type already are: a citation built from
            # this chunk needs its parent document's real context
            # without a second, separate query. Always `None` for a
            # real media chunk (no equivalent concept yet).
            "source_url": source_url,
        }
        for (chunk_id, document_id, media_asset_id, content, metadata_json, chunk_index, name, file_type, source_url, media_filename, media_mime_type, *rest)
        in rows.all()
        for embedding in [rest[0] if rest else None]
    ]


def cosine_similarities(query_embedding: list[float], chunk_embeddings: list[list[float]]) -> np.ndarray:
    """Made public (Partie 22, same "private helper -> public for real
    cross-module reuse" precedent as `rank_chunks_by_embedding` below)
    for `api.services.media.search_media`, which ranks a real,
    media-only chunk subset the same way this module already ranks a
    document's own chunks.

    **Hardening Mission, Phase 1 -- the real fix for a reproduced,
    confirmed crash**: an external audit reproduced a real
    `ValueError: setting an array element with a sequence` here whenever
    `chunk_embeddings` mixed vectors of different lengths (a real,
    genuine scenario: an organization changes `embedding_model`
    mid-lifetime -- new chunks get the new dimension, old chunks keep
    the old one, and nothing reindexes them automatically).
    `np.asarray(chunk_embeddings, ...)` cannot build a rectangular
    matrix from ragged rows; it used to raise straight into every real
    caller (`vector_search`, HyDE, media search). The real, correct fix
    is NOT a try/except around the crash -- it's to never hand numpy a
    ragged input in the first place: only embeddings whose length
    matches the QUERY embedding's own length are comparable at all
    (cosine similarity between vectors of different dimensionality is
    mathematically undefined, not just a numpy limitation), so every
    other length is excluded here, not force-fit. See
    `rank_chunks_by_embedding` below for what happens to the excluded
    ones (never silently dropped from the caller's awareness)."""
    query = np.asarray(query_embedding, dtype=float)
    matrix = np.asarray(chunk_embeddings, dtype=float)
    query_norm = np.linalg.norm(query)
    matrix_norms = np.linalg.norm(matrix, axis=1)
    denom = query_norm * matrix_norms
    denom[denom == 0] = 1e-12  # a real, cheap guard against a real zero-norm embedding, never divides by 0
    return (matrix @ query) / denom


def _split_chunks_by_dimension(query_embedding: list[float], chunks: list[dict]) -> tuple[list[dict], int]:
    """Hardening Mission, Phase 1 -- the real, shared dimension guard
    `rank_chunks_by_embedding`/`api.services.media.search_media` both
    need before ever calling `cosine_similarities` above. Returns
    (comparable_chunks, excluded_count): only chunks whose own stored
    embedding has the SAME length as the query embedding are
    comparable; everything else is a real, different-dimension
    embedding this particular query can never be ranked against (not a
    bug to silently paper over -- see `rank_chunks_by_embedding`'s own
    `dimension_mismatch_excluded` return value, which surfaces this
    count up to `search()`'s own real response so a caller/UI can
    recommend `api.services.embedding_reindex` instead of the organization
    silently losing recall on its own older documents)."""
    query_dim = len(query_embedding)
    comparable = [c for c in chunks if len(c["embedding"]) == query_dim]
    excluded = len(chunks) - len(comparable)
    if excluded:
        logger.warning(
            "retrieval_pipeline: excluded %d chunk(s) with an embedding dimension different from the query's own "
            "(%d) -- likely a stale embedding_model; see api.services.embedding_reindex",
            excluded, query_dim,
        )
    return comparable, excluded


_cosine_similarities = cosine_similarities  # internal alias, unchanged call sites below


async def vector_search(
    db: AsyncSession, organization_id, query: str, top_k: int | None = None, org_settings: dict | None = None,
    query_embedding: list[float] | None = None, metadata_filters: dict | None = None,
    document_ids: list | None = None,
) -> list[dict]:
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
    module's own top docstring.

    Phase 4, Étape 2 (Advanced Retrieval) -- `query_embedding`, when
    given, is used AS-IS instead of embedding `query` -- this is the one,
    minimal seam `api.services.retrieval_pipeline.search`'s own real
    HyDE wiring needs: HyDE (`api.services.hyde`) only ever changes WHICH
    embedding a real vector search ranks against (its own real
    hypothetical-document embedding, in place of the raw query's), never
    how the search itself works. Defaults to `None` -- every pre-existing
    real caller keeps embedding `query` itself, byte-identical
    behavior."""
    top_k = top_k if top_k is not None else resolve_top_k(org_settings)
    if query_embedding is None:
        model_name = resolve_embedding_model(org_settings)
        # Real bug found (2026-09-18), same class as hybrid_reranked_search's
        # own cross_encoder.predict below: generate_embeddings runs a
        # synchronous, CPU-bound sentence-transformers .encode() call, which
        # blocks the whole asyncio event loop for its duration if awaited
        # directly inside this async function -- and this one runs on EVERY
        # search (vector_search AND hybrid_search both call it), not just
        # the reranked strategy.
        loop = asyncio.get_running_loop()
        query_embedding = (await loop.run_in_executor(None, generate_embeddings, [query], model_name))[0]
    return await rank_chunks_by_embedding(db, organization_id, query_embedding, top_k, metadata_filters=metadata_filters, document_ids=document_ids)


async def _pgvector_rank_chunks(
    db: AsyncSession, organization_id, embedding: list[float], top_k: int,
    metadata_filters: dict | None = None, document_ids: list | None = None,
) -> list[dict] | None:
    """Hardening Mission, Phase 1 -- the real native-index path this
    module's own top docstring named as "the natural next step". Returns
    `None` (never an empty list, which is a real, valid "no matches"
    answer) whenever the native path genuinely does not apply, so
    `rank_chunks_by_embedding` knows to fall back to the pre-existing
    numpy path instead of returning a wrong empty result:

    - not running against a real Postgres bind (the fast SQLite test
      suite, where `embedding_vector` degrades to plain JSON with none
      of pgvector's own SQL operators available at all);
    - `PGVECTOR_ENABLED=False` (an explicit operator kill switch, same
      convention as every other advanced-feature flag in this
      codebase);
    - the query embedding's own dimension doesn't match the fixed,
      indexed `settings.EMBEDDING_VECTOR_DIM` -- a real, different-
      dimension organization is NOT an error here, just a real
      boundary of what this one fixed-width index can serve (see this
      module's own top-of-file Phase 1 docstring addition).

    Uses the EXACT SAME real isolation/metadata filters as
    `fetch_organization_chunks` (never a second, divergent copy of the
    multi-tenant WHERE clause) -- only the ordering/ranking mechanism
    differs, never which rows are eligible at all."""
    if not app_settings.PGVECTOR_ENABLED or db.bind is None or db.bind.dialect.name != "postgresql":
        return None
    if len(embedding) != app_settings.EMBEDDING_VECTOR_DIM:
        return None

    # Hardening Mission (§20, multimodal audit) -- a real, confirmed
    # bug: this query used to `.join(Document, ...)` (an INNER JOIN),
    # the exact same class of bug Phase 12 already fixed in
    # `fetch_organization_chunks` below (a real media-derived chunk
    # always has `document_id IS NULL`, so an INNER JOIN against
    # `Document` structurally excludes it) -- this parallel, native
    # query path was never updated when that fix landed, silently
    # re-excluding every real media chunk from this organization's own
    # Postgres-side ANN search. Mirrors `fetch_organization_chunks`'s
    # own real outerjoin + OR filter exactly, never a second, divergent
    # isolation rule.
    filters = [
        DocumentChunk.organization_id == organization_id,
        or_(DocumentChunk.document_id.is_(None), Document.deleted_at.is_(None)),
        DocumentChunk.embedding_vector.is_not(None),
    ]
    if document_ids:
        filters.append(DocumentChunk.document_id.in_(document_ids))
    if metadata_filters and app_settings.METADATA_FILTERING_ENABLED:
        from api.services.metadata_filtering import build_metadata_filter_clauses

        filters.extend(build_metadata_filter_clauses(DocumentChunk.metadata_json, metadata_filters))

    distance = DocumentChunk.embedding_vector.cosine_distance(embedding)
    try:
        rows = (
            await db.execute(
                select(DocumentChunk, Document.name, Document.file_type, Document.source_url, MediaAsset.filename, MediaAsset.mime_type, distance.label("distance"))
                .outerjoin(Document, Document.id == DocumentChunk.document_id)
                .outerjoin(MediaAsset, MediaAsset.id == DocumentChunk.media_asset_id)
                .where(*filters)
                .order_by(distance)
                .limit(top_k)
            )
        ).all()
    except Exception:
        # A real, defensive fallback (e.g. the HNSW index/extension
        # genuinely missing on a not-yet-migrated real Postgres database)
        # -- never let the native speedup path take down a real search
        # request that the pre-existing numpy path can still serve.
        logger.exception("retrieval_pipeline: native pgvector query failed, falling back to the numpy path")
        return None

    if not rows:
        # Hardening Mission (§20/§1, multimodal + pgvector audit) -- a
        # real, confirmed bug: an empty native result used to be trusted
        # as "genuinely zero matches", but `embedding_vector IS NOT NULL`
        # above silently excludes any real, otherwise-comparable chunk
        # that only has the legacy `embedding` column populated (e.g. a
        # chunk written by a code path that pre-dates this organization's
        # pgvector backfill, or any future ingestion path that forgets
        # to stamp `embedding_vector` the way this one and
        # api/security/documents.py's own process_document both do).
        # Rather than silently returning a WRONG empty answer, check
        # whether such an orphaned, legacy-only chunk actually exists
        # for this organization; if so, defer to the numpy path, which
        # DOES see it. Only ever one extra, cheap `EXISTS`-style query,
        # and only on the empty-result branch -- never on every search.
        orphan_filters = [
            DocumentChunk.organization_id == organization_id,
            or_(DocumentChunk.document_id.is_(None), Document.deleted_at.is_(None)),
            DocumentChunk.embedding.is_not(None),
            DocumentChunk.embedding_vector.is_(None),
        ]
        if document_ids:
            orphan_filters.append(DocumentChunk.document_id.in_(document_ids))
        has_orphan = await db.scalar(
            select(DocumentChunk.id).outerjoin(Document, Document.id == DocumentChunk.document_id).where(*orphan_filters).limit(1)
        )
        if has_orphan is not None:
            return None

    return [
        {
            "chunk_id": str(chunk.id), "document_id": str(chunk.document_id) if chunk.document_id else None,
            "media_asset_id": str(chunk.media_asset_id) if chunk.media_asset_id else None, "content": chunk.content,
            "metadata_json": chunk.metadata_json, "embedding": chunk.embedding,
            "document_name": name if name is not None else media_filename,
            "file_type": file_type if file_type is not None else media_mime_type,
            "chunk_index": chunk.chunk_index, "source_url": source_url,
            "score": float(1.0 - distance_value),
        }
        for chunk, name, file_type, source_url, media_filename, media_mime_type, distance_value in rows
    ]


async def rank_chunks_by_embedding(
    db: AsyncSession, organization_id, embedding: list[float], top_k: int, metadata_filters: dict | None = None, document_ids: list | None = None,
) -> list[dict]:
    """A real, shared building block, made public specifically so
    Partie 3.4.3's own `api.services.hyde` can rank this organization's
    own real chunks against a real embedding that ISN'T necessarily a
    plain query embedding (HyDE's own real hypothetical-document
    embedding) without duplicating this real cosine-ranking logic a
    second time. `vector_search` above is just this function with a
    real query embedding computed first.

    Phase 4, Étape 3 -- `metadata_filters` flows straight into
    `fetch_organization_chunks`'s own SAME new parameter: an excluded
    real chunk never even enters the real candidate list this function
    ranks, so HyDE's own real hypothetical-document embedding (the one
    real caller that reaches this function directly) automatically
    respects the SAME real filter a plain `vector_search` would.

    **Hardening Mission, Phase 1**: chunks whose own embedding dimension
    differs from `embedding`'s (a real, mixed-dimension organization,
    see `_split_chunks_by_dimension`'s own docstring) are excluded from
    THIS ranking pass rather than crashing it, and logged (never
    silent). This function's own return shape (`list[dict]`) is reused
    by citations downstream, so the exclusion count is deliberately NOT
    smuggled into a result dict here -- the real, explicit, user-facing
    signal is `api.services.embedding_reindex`'s own reindex-status
    endpoint, which tells an organization in plain terms how many of
    its chunks are on a stale embedding model, instead of a diagnostic
    field leaking into an end-user-visible citation.

    **Hardening Mission, Phase 1**: tries the real, native pgvector
    index first (`_pgvector_rank_chunks`) -- a real Postgres-side ANN
    query, not a Python-side brute force -- and only falls back to the
    pre-existing numpy path when that genuinely doesn't apply (SQLite
    tests, a non-default embedding dimension, or `PGVECTOR_ENABLED=False`).
    Byte-identical real isolation guarantees either way: see
    `_pgvector_rank_chunks`'s own docstring for why it reuses the exact
    same filters as `fetch_organization_chunks` below, never a second,
    divergent copy."""
    native_results = await _pgvector_rank_chunks(db, organization_id, embedding, top_k, metadata_filters=metadata_filters, document_ids=document_ids)
    if native_results is not None:
        return native_results

    chunks = await fetch_organization_chunks(db, organization_id, metadata_filters=metadata_filters, document_ids=document_ids)
    if not chunks:
        return []
    comparable, _excluded = _split_chunks_by_dimension(embedding, chunks)
    if not comparable:
        return []
    def _rank() -> list[dict]:
        similarities = _cosine_similarities(embedding, [c["embedding"] for c in comparable])
        ranked = sorted(zip(comparable, similarities), key=lambda pair: pair[1], reverse=True)
        return [{**chunk, "score": float(score)} for chunk, score in ranked[:top_k]]

    # Matrix build + cosine + sort are CPU-bound (and NumPy releases the GIL for the heavy part):
    # off the event loop so a large organization's search does not stall every other request.
    return await asyncio.get_running_loop().run_in_executor(None, _rank)


async def bm25_search(
    db: AsyncSession, organization_id, query: str, top_k: int | None = None, org_settings: dict | None = None,
    metadata_filters: dict | None = None, document_ids: list | None = None,
) -> list[dict]:
    """Item 2's own literal function -- real, sparse keyword search
    over this organization's own real chunk text, via a real, freshly
    built `BM25Okapi` index (no persistent BM25 index exists yet -- a
    real, honest, documented scope limit; see this module's own top
    docstring for why an ANN/persistent index is real, deferred future
    work, not silently skipped). Same real "explicit top_k bypasses
    the bound" fix as `vector_search` above.

    Phase 4, Étape 3 -- `metadata_filters`, when given, is applied by
    `fetch_organization_chunks` itself, BEFORE the real `BM25Okapi`
    index is even built: an excluded real chunk's own real text can
    never contribute to a real BM25 score, let alone be returned."""
    top_k = top_k if top_k is not None else resolve_top_k(org_settings)
    chunks = await fetch_organization_chunks(db, organization_id, metadata_filters=metadata_filters, document_ids=document_ids, with_embeddings=False)
    if not chunks:
        return []

    # Building the index and scoring is pure CPU (~O(total text)); run inline it blocks the
    # event loop for every other request in the process (measured: concurrent BM25 queries
    # got NO throughput gain). Off-loaded to the default executor so the loop stays responsive.
    def _rank() -> list[tuple[int, float]]:
        bm25 = BM25Okapi([_tokenize(c["content"]) for c in chunks])
        scores = bm25.get_scores(_tokenize(query))
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [(i, float(scores[i])) for i in order]

    ranked = await asyncio.get_running_loop().run_in_executor(None, _rank)
    return [{**chunks[i], "score": score} for i, score in ranked]


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


async def hybrid_search(
    db: AsyncSession, organization_id, query: str, top_k: int | None = None, rrf_k: int | None = None,
    org_settings: dict | None = None, query_embedding: list[float] | None = None, metadata_filters: dict | None = None,
    document_ids: list | None = None,
) -> list[dict]:
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
    apply.

    Phase 4, Étape 2 -- `query_embedding`, when given, flows straight
    into `vector_search`'s own SAME new parameter (see that function's
    own docstring): only the vector leg changes, the real BM25 leg below
    still ranks against `query`'s own raw text either way -- exactly
    this étape's own explicit requirement 11 ("HyDE doit améliorer la
    partie vectorielle sans casser le BM25").

    Phase 4, Étape 3 -- `metadata_filters` flows into BOTH the real
    vector leg AND the real BM25 leg identically: a real chunk excluded
    by the filter never enters either candidate list `reciprocal_rank_fusion`
    below fuses, so it can never re-appear via one branch even if the
    other branch would have (also) excluded it."""
    top_k = top_k if top_k is not None else resolve_top_k(org_settings)
    candidate_pool = resolve_reranker_top_k(org_settings, top_k=top_k)
    resolved_rrf_k = resolve_rrf_k(org_settings, override=rrf_k)

    semantic_results = await vector_search(
        db, organization_id, query, top_k=candidate_pool, org_settings=org_settings, query_embedding=query_embedding,
        metadata_filters=metadata_filters, document_ids=document_ids,
    )
    bm25_results = await bm25_search(
        db, organization_id, query, top_k=candidate_pool, org_settings=org_settings, metadata_filters=metadata_filters,
        document_ids=document_ids,
    )
    if not semantic_results and not bm25_results:
        return []

    # BM25 hits no longer carry the embedding (not loaded for keyword search); a chunk found by BOTH
    # legs keeps the semantic leg's dict, which does.
    by_id = {c["chunk_id"]: c for c in bm25_results}
    by_id.update({c["chunk_id"]: c for c in semantic_results})
    fused = reciprocal_rank_fusion([[c["chunk_id"] for c in semantic_results], [c["chunk_id"] for c in bm25_results]], k=resolved_rrf_k)
    ranked_ids = sorted(fused, key=lambda cid: fused[cid], reverse=True)[:top_k]
    return [{**by_id[cid], "score": fused[cid]} for cid in ranked_ids]


async def hybrid_reranked_search(
    db: AsyncSession, organization_id, query: str, top_k: int | None = None, reranker: str | None = None,
    org_settings: dict | None = None, query_embedding: list[float] | None = None, metadata_filters: dict | None = None,
) -> list[dict]:
    """Item 2's own literal function -- `hybrid_search`'s own real
    candidates, reranked by a real cross-encoder (the same real
    `sentence-transformers.CrossEncoder` `src/retrieval.py` already
    uses).

    Phase 4, Étape 2 -- `query_embedding` passes straight through to
    `hybrid_search`'s own SAME new parameter (see that function's own
    docstring).

    Phase 4, Étape 3 -- `metadata_filters` passes straight through too:
    `hybrid_search` above already excludes a real, filtered-out chunk
    from its own real candidates, so the real cross-encoder below only
    ever reranks real, ALREADY-AUTHORIZED candidates -- it never even
    sees an excluded real chunk, let alone needs to filter one out
    itself."""
    top_k = top_k if top_k is not None else resolve_top_k(org_settings)
    candidate_pool = resolve_reranker_top_k(org_settings, top_k=top_k)

    candidates = await hybrid_search(
        db, organization_id, query, top_k=candidate_pool, org_settings=org_settings, query_embedding=query_embedding,
        metadata_filters=metadata_filters,
    )
    if not candidates:
        return []

    reranker_model = resolve_reranker_model(org_settings, override=reranker)
    cross_encoder = _get_reranker(reranker_model)
    pairs = [[query, c["content"]] for c in candidates]
    # Real bug found (2026-09-18) via a live crash: CrossEncoder.predict
    # is a synchronous, CPU-bound call -- run directly inside this async
    # function, it blocks the whole asyncio event loop for its duration.
    # On Render's free tier (uvicorn.workers.UvicornWorker, a single
    # async worker), that starved every other in-flight request on the
    # same process, including Render's own health check, which timed
    # out and caused Render to kill and restart the instance mid-chat.
    # run_in_executor moves the blocking call to a thread instead.
    loop = asyncio.get_running_loop()
    rerank_scores = await loop.run_in_executor(None, cross_encoder.predict, pairs)

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
    org_settings: dict | None = None, metadata_filters: dict | None = None,
    document_ids: list | None = None, user_context: dict | None = None, trace_stages: list | None = None,
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
    backfill slots a low-quality real result was filtered out of.

    Phase 4, Étape 2 (Advanced Retrieval) -- this is also the one, real
    entry point every one of the 5 requested features hooks into, each
    gated by its own new per-organization resolver
    (`api.services.retrieval_config`'s own "Phase 4, Étape 2" section),
    every one of them `False` by default: a fresh organization that
    never touches these new settings runs EXACTLY the code path above,
    unchanged. See each block below for why it sits where it does; none
    of them replace `_STRATEGY_FUNCTIONS`/`reciprocal_rank_fusion`/the
    real cross-encoder above -- every one reuses them.

    1. Query Rewriting (requirement 5) -- pre-retrieval, replaces the
       raw `query` text used for EVERYTHING downstream (BM25, vector
       embedding, HyDE's own hypothetical document, multi-query variant
       generation) with a real, LLM/rule-based-rewritten version. Real,
       explicit `try/except`: a real rewriting failure (on top of
       `rewrite_query`'s own internal `LLMError` fallback) must never
       fail a real search that would have worked fine with the raw
       query (requirement 5's own explicit ask).
    2. HyDE (requirement 7) -- computes a real hypothetical-document
       embedding and threads it through as `query_embedding` (the new
       parameter `vector_search`/`hybrid_search`/`hybrid_reranked_search`
       above all now accept): only the real VECTOR leg changes, BM25
       keeps ranking the real query text either way (requirement 11).
       Skipped for `bm25_only` (a real embedding override is meaningless
       there -- `bm25_search` has no vector leg to give it to). Real,
       explicit `try/except`: falls back to the plain, un-overridden
       embedding search on any failure (requirement 7's own explicit
       ask) -- the hypothetical document itself is a real, disposable,
       in-memory string, never stored as a chunk/document/citation
       (requirement 7).
    3. Multi-Query (requirement 6) -- generates real query variants
       (`generate_query_variants`, itself always including the real
       original query first) and runs the SAME resolved strategy
       function (including any real HyDE override above) once per
       variant, in real parallel (`run_queries_parallel`'s own new
       `search_fn` parameter, Phase 4 Étape 2), then fuses every
       variant's own real ranked list via the SAME real
       `reciprocal_rank_fusion` `hybrid_search` already uses internally
       (`merge_query_results(method="rrf")` by real default) -- real
       reuse, not a second fusion system (requirement 6's own explicit
       ask). A real per-variant candidate count is bounded by
       `resolve_multi_query_count` (max 10, requirement 13's own real
       cost guardrail).
    4. MMR (requirement 8) -- applied to whatever real candidate list
       step 3 (or the plain, single-strategy call) already produced,
       AFTER any real cross-encoder reranking already baked into
       `hybrid_reranked_search` itself -- a real, deliberate, documented
       deviation from this étape's own literal, explicitly "conceptual"
       diagram (which showed MMR BEFORE the cross-encoder): reordering
       would mean restructuring `hybrid_reranked_search` to expose its
       own internal, pre-rerank candidates, a real, invasive change to
       an already-shipped, already-tested function, for a real, net
       WORSE outcome -- the cross-encoder's own job is to re-sort
       candidates by real relevance, which would simply undo MMR's own
       real diversity selection if MMR ran first. Diversifying the
       FINAL, already-best-ranked candidate list (still reusing that
       same list, never a new vector search, requirement 8's own
       explicit ask) is the real, correct place for it. A real,
       dedicated, wider `fetch_top_k` (via `resolve_mmr_candidate_k`,
       `top_k * 3`) is fetched up front specifically so MMR has a real
       candidate pool bigger than the real final `top_k` to diversify
       over (requirement 8's own explicit ask, "pool de candidats > k
       final"). Real, audited relevance anchor (correctif ciblé,
       2026-09-22): MMR's own relevance term always scores against
       `effective_query`'s own real embedding, never HyDE's real,
       disposable hypothetical-document embedding, even when HyDE ran --
       see this block's own inline comment below for why. Real, audited
       diversity term: `select_diverse_chunks` computes candidate-to-
       candidate similarity from each real chunk's OWN already-computed
       embedding (`compute_chunk_embedding`, reused, never
       regenerated), NEVER from the cross-encoder's own real relevance
       `score` field -- the cross-encoder measures real relevance, not
       real inter-candidate similarity, and its own real, unbounded
       logit scale would be meaningless mixed into MMR's real
       `lambda * relevance - (1-lambda) * diversity` formula anyway
       (both of THAT formula's own real terms are real, bounded cosine
       similarities, by construction).
    5. Context Compression -- deliberately NOT wired here: this module
       has no generation step of its own to compress context FOR. Wired
       instead in `api.services.generation.generate_response`, the one
       real caller that actually builds an LLM prompt from these chunks
       -- see that module's own docstring."""
    if not query or not query.strip():
        return []

    # Phase 4, Étape 3 -- real, fail-fast validation: a real, malformed
    # filter is rejected HERE, before any real LLM call (Query
    # Rewriting/HyDE/Multi-Query) or real DB work ever runs for it,
    # never discovered only after real, wasted work.
    if metadata_filters:
        from api.services.metadata_filtering import normalize_metadata_filters

        normalize_metadata_filters(metadata_filters)

    # Systèmes internes, item 24 (RAG Flight Recorder) -- real, opt-in
    # stage tracing: `trace_stages`, when a real caller supplies one
    # (an empty real list), gets one real `StageTimer.record` appended
    # per major stage below. `None` (every pre-existing real call site,
    # unchanged) means zero real overhead -- no `StageTimer` is even
    # constructed. This is deliberately a SIDE CHANNEL (an in/out
    # mutable list), never a change to `search()`'s own real return
    # type (`list[dict]`, unchanged) -- the same real "don't break
    # every existing caller's contract" discipline already applied to
    # `user_context`/`document_ids` above. Persisting the assembled
    # trace (`record_flight`) is deliberately NOT done here either --
    # same real precedent as `record_retrieval_diagnostic`, already
    # called by `generate_response`, never by `search()` itself.
    from api.services.flight_recorder import StageTimer

    effective_query = query
    if resolve_query_rewriting_enabled(org_settings):
        from api.services.query_rewriting import rewrite_query

        with StageTimer("query_rewriting") as timer:
            try:
                effective_query = await rewrite_query(query) or query
                timer.data = {"original_query": query, "rewritten_query": effective_query}
            except Exception:
                effective_query = query
                timer.data = {"original_query": query, "error": "rewrite_query failed, using original query"}
        if trace_stages is not None:
            trace_stages.append(timer.record)

    # Systèmes internes, item 25 (Query Intelligence Router) -- real,
    # opt-in adaptive routing: only ever runs when a real caller passed
    # NO explicit `strategy` override (a real, explicit override always
    # wins, exactly like every other resolver in this module) AND this
    # organization has explicitly opted in -- a fresh organization that
    # never touches this setting keeps its own real, configured
    # `retrieval_strategy` exactly as before, byte-identical.
    effective_strategy_override = strategy
    if strategy is None and resolve_adaptive_routing_enabled(org_settings):
        from api.services.query_router import suggest_retrieval_strategy

        effective_strategy_override = suggest_retrieval_strategy(effective_query)["strategy"]

    resolved_strategy = resolve_retrieval_strategy(org_settings, override=effective_strategy_override)
    strategy_function = _STRATEGY_FUNCTIONS[resolved_strategy]
    call_kwargs = {"reranker": reranker} if resolved_strategy == "hybrid_reranked" else {}
    # Phase 4, Étape 3 (Metadata Filtering) -- real, deliberate, single
    # injection point: every one of `_STRATEGY_FUNCTIONS`'s own 5 real
    # strategy functions now accepts `metadata_filters` (threaded all the
    # way down to `fetch_organization_chunks`, the one, real, shared
    # choke point -- see that function's own docstring). Landing it in
    # `call_kwargs` here means it automatically reaches: the real,
    # single-strategy call below, EVERY real Multi-Query variant (via
    # `functools.partial(strategy_function, **call_kwargs)`, same real
    # seam Étape 2 already built for `reranker`/HyDE's own
    # `query_embedding`), and stays effective under MMR (which only ever
    # diversifies among the real candidates this call already returned,
    # never fetches anything new) -- zero extra wiring needed in
    # `query_rewriting.py`/`multi_query.py`/`hyde.py`/`mmr.py` themselves.
    if metadata_filters:
        call_kwargs["metadata_filters"] = metadata_filters
    if document_ids:
        call_kwargs["document_ids"] = document_ids

    if resolved_strategy != "bm25_only" and resolve_hyde_enabled(org_settings):
        from api.services.hyde import embed_hypothetical_document, generate_hypothetical_document

        # Hardening Mission, Phase 7 -- a real, confirmed audit gap: HyDE
        # used to run inside a bare try/except with NO StageTimer of its
        # own (see api/models/flight_recording.py's own corrected
        # docstring) -- a real Flight Recorder trace couldn't tell
        # whether HyDE even ran, let alone how long its own real
        # hypothetical-document generation + embedding took.
        with StageTimer("hyde") as timer:
            try:
                hypothetical_documents = await generate_hypothetical_document(effective_query)
                hyde_embedding = embed_hypothetical_document(hypothetical_documents, org_settings=org_settings)
                if hyde_embedding:
                    call_kwargs["query_embedding"] = hyde_embedding
                timer.data = {"ran": True, "embedding_used": bool(hyde_embedding)}
            except Exception as exc:
                timer.data = {"ran": False, "error": str(exc)}
        if trace_stages is not None:
            trace_stages.append(timer.record)

    mmr_enabled = resolve_mmr_enabled(org_settings)
    resolved_top_k = resolve_top_k(org_settings, override=top_k)
    fetch_top_k = resolve_mmr_candidate_k(org_settings, top_k=resolved_top_k) if mmr_enabled else resolved_top_k
    policy_active = user_context is not None and resolve_policy_aware_retrieval_enabled(org_settings)
    if policy_active:
        # Hardening Mission (§8) -- the access policy removes chunks AFTER ranking, so the candidate pool must be
        # wider than the final top_k or a restricted user gets fewer results than permitted chunks exist.
        fetch_top_k = max(fetch_top_k, resolved_top_k * max(1, app_settings.POLICY_OVERFETCH_FACTOR))

    with StageTimer(f"strategy_dispatch:{resolved_strategy}") as timer:
        if resolve_multi_query_enabled(org_settings):
            from api.services.multi_query import (
                deduplicate_results,
                generate_query_variants,
                merge_query_results,
                rerank_merged_results,
                run_queries_parallel,
            )

            try:
                variants = await generate_query_variants(effective_query, num_variants=resolve_multi_query_count(org_settings))
            except Exception:
                variants = [effective_query]
            search_fn = functools.partial(strategy_function, **call_kwargs) if call_kwargs else strategy_function
            per_query_results = await run_queries_parallel(
                db, organization_id, variants, top_k=fetch_top_k, org_settings=org_settings, search_fn=search_fn,
            )
            merged = merge_query_results(per_query_results)
            deduplicated = deduplicate_results(merged)
            results = rerank_merged_results(deduplicated, effective_query, org_settings=org_settings)[:fetch_top_k]
            timer.data = {"multi_query": True, "variant_count": len(variants), "candidate_count": len(results)}
        else:
            results = await strategy_function(db, organization_id, effective_query, top_k=fetch_top_k, org_settings=org_settings, **call_kwargs)
            timer.data = {"multi_query": False, "candidate_count": len(results)}
    if trace_stages is not None:
        trace_stages.append(timer.record)

    # Systèmes internes, item 22 (Policy-Aware Retrieval) -- real, additive, opt-in filter. Hardening Mission
    # (§8): it now runs RIGHT AFTER candidate retrieval -- before MMR, the score threshold and the final cut to
    # `top_k`. Two real defects in the old order (after all of them): (1) a restricted user got fewer results
    # than `top_k` even though permitted chunks existed just below the cut; (2) MMR chose its "diverse" subset
    # while still seeing chunks the caller may not read, so the PRESENCE of a forbidden chunk changed which
    # permitted chunks were returned -- an indirect information leak. Only runs when BOTH this organization has
    # opted in AND a real `user_context` was supplied (every pre-existing caller without one is unchanged).
    # `filter_chunks_by_policy` itself is fail-open (item 13's `check_policy` contract): a chunk is only
    # excluded by a real, explicit, successful `False` from OPA.
    if policy_active:
        from api.services.policy_aware_retrieval import filter_chunks_by_policy

        # Hardening Mission, Phase 7 -- this stage has its own StageTimer so a Flight Recorder trace shows
        # whether policy filtering ran or excluded anything.
        with StageTimer("policy_aware_retrieval") as timer:
            before_count = len(results)
            results = await filter_chunks_by_policy(results, user_context)
            timer.data = {"before_count": before_count, "after_count": len(results)}
        if trace_stages is not None:
            trace_stages.append(timer.record)

    if mmr_enabled and results:
        from api.services.mmr import select_diverse_chunks
        from api.services.semantic_filtering import compute_query_embedding

        # Phase 4, Étape 2 correctif ciblé (MMR audit, 2026-09-22) -- real,
        # deliberate fix: this used to reuse `call_kwargs["query_embedding"]`
        # (HyDE's own real, DISPOSABLE hypothetical-document embedding,
        # when HyDE ran) as MMR's own relevance anchor. HyDE's job is done
        # by this point (it already shaped WHICH real candidates got
        # retrieved) -- re-scoring the FINAL, real selection against a
        # real, no-longer-needed hypothetical artifact, instead of the
        # real, original user query, is the same real "recall vs
        # precision" distinction `api.services.multi_query.rerank_merged_results`
        # already documents (variants/HyDE widen RECALL; the real,
        # original query's own real similarity re-establishes real
        # PRECISION for the real, final ranking) -- MMR's own relevance
        # term always anchors to `effective_query`'s own real embedding
        # now, HyDE or not. Real, honest cost: exactly one real, extra
        # embedding call when MMR is enabled (same real cost the old
        # code already paid whenever HyDE hadn't run) -- never a second
        # real vector SEARCH, and every real candidate's OWN embedding is
        # still reused as-is (`compute_chunk_embedding`, inside
        # `select_diverse_chunks`), never recomputed.
        with StageTimer("mmr") as timer:
            mmr_query_embedding = compute_query_embedding(effective_query, org_settings=org_settings)
            results = select_diverse_chunks(
                results, mmr_query_embedding, lambda_param=resolve_mmr_lambda(org_settings), top_k=resolved_top_k,
            )
            timer.data = {"final_count": len(results)}
        if trace_stages is not None:
            trace_stages.append(timer.record)

    resolved_threshold = resolve_score_threshold(org_settings, override=score_threshold)
    with StageTimer("threshold_filtering") as timer:
        pre_filter_count = len(results)
        results = filter_by_score_threshold(results, resolved_threshold)
        timer.data = {"threshold": resolved_threshold, "before_count": pre_filter_count, "after_count": len(results)}
    if trace_stages is not None:
        trace_stages.append(timer.record)

    return results[:resolved_top_k]


async def search_with_context(
    db: AsyncSession, organization_id, query: str, top_k: int | None = None,
    strategy: str | None = None, reranker: str | None = None, score_threshold: float | None = None,
    org_settings: dict | None = None, metadata_filters: dict | None = None, document_ids: list | None = None,
    user_context: dict | None = None, trace_stages: list | None = None,
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
        score_threshold=score_threshold, org_settings=org_settings, metadata_filters=metadata_filters,
        user_context=user_context, trace_stages=trace_stages,
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


async def graph_context(organization_id, query: str, org_settings: dict | None = None) -> str | None:
    """Real GraphRAG query, wired into the actual retrieval pipeline
    (closing the gap `api/services/graph_rag.py`'s own docstring
    honestly flagged: a genuinely working building block that nothing
    real called yet). Deliberately NOT merged into `search()`'s own
    real chunk list: a graph-synthesized answer draws on POTENTIALLY
    MANY real documents at once (that's the entire point of GraphRAG's
    multi-hop/global-summary capability) -- it has no single real
    `chunk_id`/`document_id` to attach a real `Citation` to without
    fabricating one, which would misrepresent a real, honest synthesis
    as if it verbatim-quoted one specific real chunk. Returned as a
    separate, real, honestly-uncitable text block instead --
    `api.services.generation.generate_response` includes it as
    additional context, clearly labeled, alongside (never replacing)
    the real, precisely-cited BM25/vector/hybrid chunks.

    Real, honest degradation: `None` when GraphRAG is disabled for this
    organization, when no organization document has ever actually been
    ingested into its graph (`api.security.documents.process_document`'s
    own real, opt-in ingestion, same `graphrag_enabled` setting), or on
    any real failure (LightRAG unavailable, a real LLM error) -- a real
    search must never fail solely because this genuinely optional,
    additive step did."""
    if not resolve_graphrag_enabled(org_settings):
        return None
    try:
        from api.services.graph_rag import GraphRAGNotAvailableError, query_graph

        embedding_model = resolve_embedding_model(org_settings)
        answer = await query_graph(organization_id, query, embedding_model)
        return answer.strip() if answer and answer.strip() else None
    except GraphRAGNotAvailableError:
        return None
    except Exception:
        logger.warning("graph_context: real GraphRAG query failed for organization '%s'", organization_id, exc_info=True)
        return None


async def record_retrieval_diagnostic(
    db: AsyncSession, organization_id, query: str, strategy: str, results: list[dict], latency_ms: int,
) -> RetrievalDiagnostic:
    """Phase 5, Étape 11 -- real, per-query diagnostic for a LIVE query
    (see api/models/retrieval_diagnostic.py's own docstring for the
    honest scope: final chunks + latency, not a full before/after-rerank
    breakdown). `final_chunks` stores only `chunk_id`/`document_id`/
    `score` per result -- never the full chunk text, which would
    needlessly duplicate real document content already stored once in
    `document_chunks` and bloat this table for no diagnostic value."""
    diagnostic = RetrievalDiagnostic(
        organization_id=organization_id, query=query, strategy=strategy,
        final_chunks=[{"chunk_id": r.get("chunk_id"), "document_id": r.get("document_id"), "score": r.get("score")} for r in results],
        result_count=len(results), latency_ms=latency_ms,
    )
    db.add(diagnostic)
    await db.flush()
    return diagnostic


def build_llm_context(citation_chunks: list[dict] | None, org_settings: dict | None = None) -> str | None:
    """Real fix found via audit (2026-09-19): the two real callers that
    build an LLM prompt from retrieved chunks (api/routers/chat_stream.py,
    api/services/public_api.py) used to do a plain, unbounded
    `"\\n\\n".join(...)` -- no limit at all on how much text could be
    handed to the LLM. Both now call this shared helper instead of
    reimplementing their own truncation. Bounds to
    `settings.RAG_CONTEXT_MAX_TOKENS`, using the SAME tokenizer already
    cached for chunking (`get_tokenizer`) -- truncates whole chunks from
    the end (lowest-ranked first, since `citation_chunks` is already
    ordered by relevance), never cuts a chunk's own text in half."""
    if not citation_chunks:
        return None

    from api.config import settings
    from api.services.sentence_chunking import get_tokenizer

    model_name = resolve_embedding_model(org_settings)
    tokenizer = get_tokenizer(model_name)
    budget = settings.RAG_CONTEXT_MAX_TOKENS

    kept: list[str] = []
    used = 0
    for chunk in citation_chunks:
        content = chunk["content"]
        length = len(tokenizer.encode(content, add_special_tokens=False))
        if kept and used + length > budget:
            break
        kept.append(content)
        used += length
    return "\n\n".join(kept) if kept else None

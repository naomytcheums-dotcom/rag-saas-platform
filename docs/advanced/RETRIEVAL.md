# Retrieval

## Hybrid search

Retrieval combines two ranking signals rather than relying on either
alone:

- **Keyword search (BM25)** — catches exact identifiers and terms that
  embeddings can blur (e.g. specific API names, error codes).
- **Semantic search (embeddings)** — catches conceptually related
  passages that don't share exact wording with the query.

## Fusion

The two rankings are merged with **Reciprocal Rank Fusion (RRF)**,
which combines differently-scaled rankings by rank position rather than
requiring hand-tuned score weights between two incomparable scoring
systems.

## Why this combination

This exact approach — hybrid search + RRF, followed by reranking (see
[Reranking](RERANKING.md)) — was validated in the original
single-tenant demo, where it was the direct cause of a measurable
Recall@5/MRR improvement, and where a real failure analysis diagnosed
*why* the remaining baseline misses happened (5 of 6 were not a search
problem at all — the reranker was demoting correct results). See
[`src/README.md`](../../src/README.md#results) and
[`src/README.md`](../../src/README.md#where-the-baseline-failures-came-from)
for the full data.

## The exact order of the pipeline

`api/services/retrieval_pipeline.py::search()` runs these stages, in this order. Each optional stage is off unless
the organization enabled it; a fresh organization runs only the mandatory ones.

| # | Stage | Notes |
|---|---|---|
| 0 | Validate the query and any metadata filters | fail-fast, before any paid call |
| 1 | Query rewriting *(optional)* | the rewritten query replaces the raw one for everything below |
| 2 | Strategy choice | explicit override > adaptive routing *(optional)* > organization setting |
| 3 | HyDE *(optional)* | only changes the **vector** leg's embedding; BM25 keeps ranking the query text |
| 4 | Candidate retrieval — `top_k` becomes the **pool size** `fetch_top_k` | the pool is `top_k`; **x3 when MMR is on**; **x`POLICY_OVERFETCH_FACTOR` (3) when access policies apply** (the larger wins) |
| 4a | Strategy: `vector_only`/`semantic`, `bm25_only`, `hybrid` (vector + BM25 fused by RRF), `hybrid_reranked` (hybrid, then cross-encoder) | with multi-query *(optional)*: one run per query variant, fused by RRF, then re-scored against the original query |
| 5 | **Access policy filter** *(when enabled and a caller identity is supplied)* | runs **before** MMR/threshold/cut, so a restricted user is backfilled from the wider pool and MMR never sees a chunk the caller may not read |
| 6 | MMR diversification *(optional)* | relevance is scored against the effective query's own embedding (never HyDE's disposable one); cuts to `top_k` |
| 7 | Score threshold | normalized scores; filters **within** the already-selected candidates (it does not fetch more to backfill) |
| 8 | Final cut to `top_k` | |

Where the vector leg runs: on PostgreSQL with the default embedding dimension it is a native pgvector (HNSW) query;
otherwise (SQLite, another dimension, `PGVECTOR_ENABLED=False`) it is an in-process cosine ranking. The BM25 leg is
always computed in process, over the organization's chunks (text only — embeddings are not loaded for it); see
`scripts/retrieval_benchmark.py` for measured costs.

Known, deliberate simplifications: the score threshold does not backfill; BM25 is rebuilt per query (a persistent
full-text index is the planned fix for very large corpora); context compression is applied at generation time, not here.

## Multi-tenant scoping

Every retrieval call is scoped to the requesting organization's
documents — search never crosses `org_id` boundaries. See
[Multi-tenancy](MULTI_TENANCY.md).

## Visual search

Image retrieval uses a different mechanism (CLIP embedding similarity,
not BM25/RRF) — see [Media & Vision](MEDIA_AND_VISION.md).

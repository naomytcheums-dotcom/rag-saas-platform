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

## Multi-tenant scoping

Every retrieval call is scoped to the requesting organization's
documents — search never crosses `org_id` boundaries. See
[Multi-tenancy](MULTI_TENANCY.md).

## Visual search

Image retrieval uses a different mechanism (CLIP embedding similarity,
not BM25/RRF) — see [Media & Vision](MEDIA_AND_VISION.md).

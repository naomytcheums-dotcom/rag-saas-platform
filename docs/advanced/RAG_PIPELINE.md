# RAG Pipeline

The multi-tenant pipeline (`api/services/`) implements the same
retrieval techniques proven out in the platform's original single-tenant
demo — see [`src/README.md`](../../src/README.md) for the full, honest
evaluation methodology and results those techniques were validated
against (Recall@5, MRR, and a real failure-analysis of every baseline
miss).

## Stages

1. **Ingestion** — document upload, text extraction. See
   [Documents API](../api/DOCUMENTS.md).
2. **Chunking** — splitting into retrieval-sized passages. See
   [Chunking](CHUNKING.md).
3. **Embedding** — each chunk embedded for semantic search. See
   [Embeddings](EMBEDDINGS.md).
4. **Retrieval** — hybrid BM25 + semantic search, fused with
   Reciprocal Rank Fusion. See [Retrieval](RETRIEVAL.md).
5. **Reranking** — a cross-encoder re-scores the fused candidate set.
   See [Reranking](RERANKING.md).
6. **Generation** — the reranked context plus the question are sent to
   an LLM (via litellm) with a citation-required prompt. Answers are
   grounded and cited — see [Citations](../user/CITATIONS.md).

## Multi-tenant adaptation

The original demo ran against one document set in a local ChromaDB
instance. The platform version scopes every stage by `org_id`
(see [Multi-tenancy](MULTI_TENANCY.md)) and stores embeddings in
PostgreSQL via `pgvector` rather than a local vector store, so retrieval
never crosses tenant boundaries.

## Evaluating pipeline changes

Any change to chunking, embeddings, retrieval, or reranking should be
run through the Evaluation Lab's regression detection before shipping —
see [`docs/CAHIER_DES_CHARGES.md`](../CAHIER_DES_CHARGES.md) (Partie 7)
and `api/routers/regression_detection.py`.

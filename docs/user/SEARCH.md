# Search

## Searching documents directly

Besides asking questions in chat, you can search your organization's
documents directly from **Documents → Search** to browse matching
passages without generating an answer.

## How search works

Search combines keyword matching (BM25) with semantic (embedding-based)
search, merges the two rankings, and reranks the result for relevance.
See [Retrieval](../advanced/RETRIEVAL.md) and
[Reranking](../advanced/RERANKING.md) for the technical detail — this
is the same technique validated in the platform's original single-tenant
evaluation, see [`src/README.md`](../../src/README.md#results).

## Visual search

If media assets (images) have been uploaded, you can search them by
image similarity or by text description — see
[Media](MEDIA.md#visual-search).

## Filters

Search can be scoped by document, workspace, or metadata filters,
depending on what's configured for your organization.

# Chunking

Documents are split into retrieval-sized passages before embedding,
rather than embedded whole — a whole document is usually too large (and
too topically diverse) for a single embedding to represent well, and
too large to hand an LLM as grounding context for one specific claim.

## Baseline approach

The original single-tenant demo (`src/indexing.py`) chunks by real
tokenizer offsets — 512 tokens per chunk, 50 tokens of overlap between
consecutive chunks — rather than a naive character-count split, so
chunk boundaries respect actual token counts for the embedding model
being used. See [`src/README.md`](../../src/README.md#architecture).

## Overlap

Overlap between consecutive chunks reduces the chance that a relevant
sentence gets split exactly at a chunk boundary and loses surrounding
context in both halves.

## Multi-tenant pipeline

The platform version applies the same chunking approach per-document,
scoped by `org_id`, as part of the background ingestion pipeline — see
[RAG Pipeline](RAG_PIPELINE.md) and [Documents](../user/DOCUMENTS.md).

## Further chunking strategies

Advanced strategies (structure-aware chunking for code/tables, semantic
chunking, variable chunk sizes per content type) are not part of the
current implementation — the fixed-size, overlap-based approach above
is what's actually running. See [`ROADMAP.md`](../../ROADMAP.md) for
what's under consideration.

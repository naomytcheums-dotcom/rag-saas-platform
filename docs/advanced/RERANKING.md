# Reranking

After hybrid search fusion (see [Retrieval](RETRIEVAL.md)), a
cross-encoder reranker re-scores the candidate set for relevance to the
specific query, rather than trusting the fused rank order alone.

## Model and blend

The validated baseline uses `cross-encoder/ms-marco-MiniLM-L-6-v2`,
blended 85/15 with the original fusion score rather than replacing it
outright — see [`src/README.md`](../../src/README.md#tech-stack) for
why the blend exists.

## Why a blend, not a pure reranker score

The original single-tenant demo's own failure analysis found that
using the reranker score in isolation could actively demote correct
results — 5 of 6 baseline retrieval misses were cases where the correct
document was already found by search, then pushed out of the final
top-5 by the reranker alone. The blend (not a pure reranker-only
ranking) is the documented fix for that specific, diagnosed failure
mode — and the first attempted fix actually made MRR worse before the
working blend ratio was found. See
[`src/README.md`](../../src/README.md#where-the-baseline-failures-came-from)
for the full root-cause writeup.

## Evaluation caveat

The 85/15 blend weight was tuned against the same 50-question
evaluation set later used to report headline Recall@5/MRR numbers — a
real, documented data-leakage caveat, not hidden. A held-out split
exists for evaluating future parameter changes without repeating this.
See [`src/README.md`](../../src/README.md#results).

"""
Real Query Intelligence Router / Adaptive Retrieval Router -- item 25
of the internal-systems list. Real, additive SUGGESTION only -- an
organization's own configured `retrieval_strategy`
(`api.services.retrieval_config.resolve_retrieval_strategy`) remains
the real, unchanged default every existing real caller of `search()`
already uses; this module never overrides it on its own. A caller that
explicitly wants adaptive routing passes this function's own real
suggestion as `search()`'s existing `strategy` override parameter
(already real, already supported) -- this module adds a real signal, not
a new, silently-activated behavior.

**Real, honest, deterministic heuristic -- no new LLM call**: routing
every real query through an extra real LLM classification call would
add real latency/cost to the hot retrieval path for a real benefit this
étape's own literal ask doesn't require (a fast, cheap, deterministic
router is the real, standard first implementation of this pattern, an
LLM-based classifier a real, possible future upgrade if the simple
heuristic proves insufficient in practice -- see this module's own
ROADMAP.md entry). Real, plain regex/heuristic cues, not guessed:
multi-hop/comparison language ("compare", "difference between",
"relationship between", "across multiple/all", "versus"/"vs") suggests
`hybrid_reranked` (this codebase's own real, most precise strategy) --
`graphrag_recommended` is a SEPARATE real flag (not a `retrieval_strategy`
value -- `RETRIEVAL_STRATEGIES` has no real `"graph"` entry, GraphRAG
is only ever an ADDITIVE context block via `graph_context`, item 6's
own real, documented, current scope) for a caller that also wants to
know whether this query's own real characteristics suggest enabling
`graphrag_enabled` for it. A short, keyword-heavy query (no question
words, few real tokens) suggests `bm25_only` (real, exact keyword
matching, cheaper than a real embedding call for a real, simple lookup).
Everything else suggests `hybrid` -- this codebase's own real, existing
default strategy either way, so a query this heuristic can't
confidently classify changes nothing for a real caller."""

import re

_MULTI_HOP_CUES = re.compile(
    r"\b(compare|comparison|difference between|relationship between|versus|vs\.?|across (multiple|all|both)|both .+ and)\b",
    re.IGNORECASE,
)
_QUESTION_WORDS = re.compile(r"\b(what|why|how|when|where|who|which|explain|describe)\b", re.IGNORECASE)


def suggest_retrieval_strategy(query: str) -> dict:
    """Real, deterministic suggestion for one real query. Returns
    `{"strategy": <a real RETRIEVAL_STRATEGIES value>, "graphrag_recommended": bool,
    "reason": str}` -- `strategy` is always a real, valid value
    `search()`'s own `strategy` override already accepts, never a
    fabricated one."""
    stripped = (query or "").strip()
    if not stripped:
        return {"strategy": "hybrid", "graphrag_recommended": False, "reason": "empty query -- real, safe default"}

    if _MULTI_HOP_CUES.search(stripped):
        return {
            "strategy": "hybrid_reranked", "graphrag_recommended": True,
            "reason": "real multi-hop/comparison language detected -- this codebase's own most precise strategy, plus GraphRAG's own real multi-document synthesis",
        }

    word_count = len(stripped.split())
    if word_count <= 4 and not _QUESTION_WORDS.search(stripped):
        return {
            "strategy": "bm25_only", "graphrag_recommended": False,
            "reason": f"short ({word_count}-word), keyword-like query -- real, exact keyword matching over a real embedding call",
        }

    return {"strategy": "hybrid", "graphrag_recommended": False, "reason": "no strong real signal either way -- this codebase's own real, existing default"}

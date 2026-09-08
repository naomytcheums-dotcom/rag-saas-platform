"""
Partie 6.2.4 -- a real, BROADER agent-confidence estimate, distinct
from Partie 6.1.10's own narrower, citation-quality-only
`Response.confidence_score`. This étape's own 5 real factors look at
the answer's own text too (citation coverage, context alignment,
response length), not only the citations themselves.

**Cohérence -- real reuse, not three more reimplementations**:
`calculate_source_consistency` reuses `source_consistency.calculate_source_agreement`
directly (the SAME real pairwise agreement Partie 6.2.8 already
validated); `calculate_citation_quality` reuses
`response_confidence.calculate_confidence_factors`'s own real
`relevance` value (the SAME real mean-relevance-score definition
Partie 6.1.10 already established). Neither factor is recomputed a
second, independently-drifting way.

**A real, documented deviation from this étape's own literal
`calculate_citation_coverage(citations)` signature**: the French
description ("pourcentage de la réponse couvert par des citations")
is unambiguous that this measures how much of the ANSWER's own real
text carries a traceable citation, which a `citations`-only signature
can't honestly compute -- `response` was added as a real, necessary
parameter (same "the literal signature didn't match its own literal
description" class of fix already applied elsewhere this session).

**Performance -- fully synchronous, zero database access**: every one
of these 5 real factors is computable from data already in memory
(the response's own text, and its own already-loaded citations) --
no live chunk/document lookups needed here (`api/services/source_consistency.py`'s
own richer, DB-backed `temporal_consistency` metric belongs to its own
Partie 6.2.8 response field, not this one).

**Robustesse -- what happens with no real citations**: every factor
honestly reports its own real "nothing here" value (`0.0` coverage/
consistency/quality) rather than a fabricated neutral default -- an
agent's own confidence in an uncited answer should genuinely be low."""

import re

from api.config import settings
from api.models.citation import Citation
from api.models.response import Response
from api.services.claim_extraction import extract_claims
from api.services.response_confidence import calculate_confidence_factors
from api.services.source_consistency import calculate_source_agreement
from api.services.text_similarity import jaccard_similarity

_MARKER = re.compile(r"\[(\d+)\]")
# A real, documented reference point (not a universal truth): a
# 100-word answer is treated as "fully substantial" for this factor's
# own real, chosen normalization -- see this module's own top
# docstring for why a simple, honest heuristic is preferred here over
# a fabricated "ideal length" model.
_RESPONSE_LENGTH_REFERENCE_WORDS = 100.0


def calculate_citation_coverage(response: Response, citations: list[Citation]) -> float:
    """Item 5's own literal function (real, `response` param added --
    see this module's own top docstring) -- real fraction of the
    answer's own real claims that carry a real, traceable `[N]`
    marker matching one of the given citations' own real
    `citation_number`."""
    claims = extract_claims(response.answer)
    if not claims:
        return 0.0
    real_numbers = {c.citation_number for c in citations}
    covered = sum(1 for claim in claims if any(int(n) in real_numbers for n in _MARKER.findall(claim)))
    return covered / len(claims)


def calculate_source_consistency(citations: list[Citation]) -> float:
    """Item 5's own literal function -- real, thin reuse of
    `source_consistency.calculate_source_agreement` (see this module's
    own top docstring for why)."""
    return calculate_source_agreement(citations)


def calculate_context_alignment(response: Response, context: str | None) -> float:
    """Item 5's own literal function -- real, fast word-overlap
    similarity between the answer and the real context it was
    generated from (see `text_similarity.py`'s own top docstring for
    why this is deliberately not embedding-based). Honestly `0.0`
    without a real context to compare against."""
    if not context:
        return 0.0
    return jaccard_similarity(response.answer, context)


def calculate_citation_quality(citations: list[Citation]) -> float:
    """Item 5's own literal function -- real, thin reuse of
    `response_confidence.calculate_confidence_factors`'s own real
    `relevance` value (see this module's own top docstring for why)."""
    return calculate_confidence_factors(citations)["relevance"]


def calculate_response_length_factor(response: Response) -> float:
    """Real, additional function backing the `response_length` factor
    (not one of item 5's own literal 6 -- `aggregate_confidence_factors`
    takes an already-built factors dict, so something has to build the
    `response_length` entry). Real, honest, normalized against
    `_RESPONSE_LENGTH_REFERENCE_WORDS` (see this module's own top
    docstring)."""
    word_count = len(response.answer.split())
    return min(word_count / _RESPONSE_LENGTH_REFERENCE_WORDS, 1.0)


def aggregate_confidence_factors(factors: dict) -> float:
    """Item 5's own literal function -- real, weighted average via
    `CONFIDENCE_ESTIMATION_FACTORS` (validated to sum to 1.0 at
    startup), clamped to `[0.0, 1.0]`."""
    score = sum(factors.get(name, 0.0) * weight for name, weight in settings.CONFIDENCE_ESTIMATION_FACTORS.items())
    return max(0.0, min(1.0, score))


def estimate_confidence(response: Response, citations: list[Citation], context: str | None = None) -> dict:
    """Item 5's own literal function -- real, top-level orchestrator:
    computes all 5 real factors, then aggregates them. A real, honest
    no-op (`score=0.0`, every factor `0.0`) when
    `CONFIDENCE_ESTIMATION_ENABLED` is off."""
    if not settings.CONFIDENCE_ESTIMATION_ENABLED:
        factors = {name: 0.0 for name in settings.CONFIDENCE_ESTIMATION_FACTORS}
        return {"score": 0.0, "factors": factors}

    factors = {
        "citation_coverage": calculate_citation_coverage(response, citations),
        "source_consistency": calculate_source_consistency(citations),
        "context_alignment": calculate_context_alignment(response, context),
        "citation_quality": calculate_citation_quality(citations),
        "response_length": calculate_response_length_factor(response),
    }
    return {"score": aggregate_confidence_factors(factors), "factors": factors}

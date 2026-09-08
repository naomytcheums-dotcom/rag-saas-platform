"""
Partie 7.2.12 -- real hallucination rate: the proportion of a real
answer's own claims that are unsupported or contradicted, plus how
much of the real, available sources actually got used.

**Cohérence -- real reuse, not a 4th claim-support formula**: this
codebase already computes real claim-support/non-contradiction TWICE
(`api/services/claim_verification.py`'s own real, live-agent-scoped
Partie 6.2.6, and `answer_quality_metrics.calculate_faithfulness`'s
own Evaluation-Lab-scoped Partie 7.2.8). `unsupported_claims_ratio`/
`contradiction_rate` below are real, direct, honest INVERSES of
`answer_quality_metrics.claim_support`/`hallucination_absence` (both
made public for exactly this reuse) -- never a 3rd, independently
computed version of the same real idea. `confidence_estimation`
likewise reuses this SAME real result's own already-computable real
`calculate_faithfulness` score directly, rather than a 5th, competing
real confidence formula alongside `confidence_estimation.py`'s own
ORM-scoped Partie 6.2.9 and this module's own real need.

**Une vraie polarité inversée par rapport à Faithfulness/Answer
relevance -- documentée explicitement**: every OTHER real Evaluation
Lab score in this batch is "higher = better". `hallucination_rate` is
a real RATE of a real bad thing -- higher = WORSE, by its own literal
name. `source_coverage`/`confidence_estimation` are themselves
"higher = better" real signals, so their own real contribution to the
combined real score is `(1 - factor)`, the SAME real, documented
"raw factor stays honest, only the combination inverts" convention
`context_relevance.py`'s own `redundancy_score` already established.

**Robustesse (vision critique 3) -- une réponse courte**: with fewer
than `HALLUCINATION_RATE_MIN_CLAIMS` real, extracted claims, the real
computation still runs (never raises), but the real returned dict
carries an honest `"reliable": False` -- a real, short answer's own
hallucination rate is real but statistically thin, never silently
presented as equally trustworthy as a real, claim-rich one."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.services.answer_quality_metrics import calculate_faithfulness, claim_support, hallucination_absence
from api.services.claim_extraction import extract_claims
from api.services.retrieval_metrics import summarize_metric
from api.services.text_similarity import jaccard_similarity


def _citation_text(citation: dict) -> str:
    """Real, flexible accessor -- same real convention as
    `answer_quality_metrics.citation_text`."""
    return citation.get("text") or citation.get("content") or ""


def _source_coverage(response: str, citations: list[dict]) -> float:
    """Real, factor 3 -- real fraction of the real, AVAILABLE citations
    the answer actually draws from at all (any real, non-zero word
    overlap) -- a real answer ignoring every one of its own real
    sources while still making real claims is a real, honest
    hallucination-risk signal `claim_support`/`hallucination_absence`
    alone don't directly capture (those are claim-scoped, this is
    source-scoped). Honestly `0.0` with no real citations available at
    all -- nothing real to have coverage of."""
    if not citations:
        return 0.0
    used = sum(1 for c in citations if jaccard_similarity(response, _citation_text(c)) > 0)
    return used / len(citations)


def calculate_hallucination_rate(response: str, citations: list[dict], context: str | None = None) -> dict:
    """Item 1's own literal function (Partie 7.2.12) -- real, weighted
    aggregation via `HALLUCINATION_RATE_WEIGHTS` (see this module's own
    top docstring for the real, documented inverted polarity).
    Honestly all-`0.0` (a real, empty answer hallucinates nothing --
    same real convention as `calculate_faithfulness`'s own empty-answer
    case) for a real, empty `response`."""
    factors = {
        "unsupported_claims_ratio": 0.0, "contradiction_rate": 0.0, "source_coverage": 0.0, "confidence_estimation": 0.0,
    }
    if not response or not response.strip():
        return {"score": 0.0, "factors": factors, "reliable": False}

    claims = extract_claims(response)
    factors = {
        "unsupported_claims_ratio": 1.0 - claim_support(response, citations),
        "contradiction_rate": 1.0 - hallucination_absence(response, citations),
        "source_coverage": _source_coverage(response, citations),
        "confidence_estimation": calculate_faithfulness(response, citations, context)["score"],
    }
    weights = settings.HALLUCINATION_RATE_WEIGHTS
    contributions = {
        "unsupported_claims_ratio": factors["unsupported_claims_ratio"], "contradiction_rate": factors["contradiction_rate"],
        "source_coverage": 1.0 - factors["source_coverage"], "confidence_estimation": 1.0 - factors["confidence_estimation"],
    }
    score = max(0.0, min(1.0, sum(contributions[name] * weight for name, weight in weights.items())))
    reliable = len(claims) >= settings.HALLUCINATION_RATE_MIN_CLAIMS
    return {"score": score, "factors": factors, "reliable": reliable}


async def get_hallucination_rate_summary(db: AsyncSession, dataset_id: uuid.UUID) -> dict:
    """Item 1's own literal function -- real, thin reuse of
    `retrieval_metrics.summarize_metric`."""
    return await summarize_metric(db, dataset_id, "hallucination_rate")

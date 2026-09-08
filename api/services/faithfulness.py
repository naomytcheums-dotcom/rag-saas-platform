"""
Partie 6.2.11 -- how faithfully an answer represents what its own
cited sources actually say, complementary to (never a duplicate of)
Partie 6.2.10's own groundedness (how MUCH the answer draws on real
sources) and Partie 6.2.9's own hallucination score (how much is
actively wrong or invented).

**Cohérence (vision critique 1) -- real reuse of 3 of its own 4
factors, avoiding a THIRD or FOURTH reimplementation of the same real
signal**: `source_fidelity` reuses `source_consistency.calculate_source_agreement`
(Partie 6.2.8) directly; `context_fidelity` reuses
`confidence_estimation.calculate_context_alignment` (Partie 6.2.4)
directly; `citation_consistency` reuses
`response_confidence.calculate_confidence_factors`'s own real,
SCORE-VARIANCE-based `consistency` (Partie 6.1.10) directly --
deliberately NOT the same real signal as `source_fidelity` (which
checks whether citation TEXTS conflict; Partie 6.1.10's own
`consistency` checks whether citation RELEVANCE SCORES agree) --
genuinely distinct, both real.

**`claim_accuracy`, the one genuinely NEW real factor**: the real
fraction of claims `claim_verification.verify_single_claim` (Partie
6.2.6) calls fully `"verified"` -- a real, STRICTER bar than Partie
6.2.10's own `groundedness.calculate_claim_support` (which counts ANY
real support, even partial, as covered).

**Robustesse (vision critique 3) -- what happens with no real
citations**: every real factor honestly reports its own real "nothing
here" value (`0.0`) -- an unfaithful-to-nothing answer is honestly not
faithful, never a fabricated neutral default."""

from api.config import settings
from api.models.citation import Citation
from api.models.response import Response
from api.services.claim_extraction import extract_claims
from api.services.claim_verification import verify_single_claim
from api.services.confidence_estimation import calculate_context_alignment
from api.services.response_confidence import calculate_confidence_factors
from api.services.source_consistency import calculate_source_agreement


def calculate_claim_accuracy(claims: list[str], citations: list[Citation]) -> float:
    """Item 5's own literal function -- real fraction of claims fully
    `"verified"` (see this module's own top docstring for why this is
    stricter than groundedness's own claim-support factor). Honestly
    `0.0` without any real claims."""
    if not claims:
        return 0.0
    return sum(1 for claim in claims if verify_single_claim(claim, citations)["status"] == "verified") / len(claims)


def calculate_source_fidelity(citations: list[Citation]) -> float:
    """Item 5's own literal function -- real, thin reuse of
    `source_consistency.calculate_source_agreement` (see this module's
    own top docstring for why)."""
    return calculate_source_agreement(citations)


def calculate_context_fidelity(response: Response, context: str | None) -> float:
    """Item 5's own literal function -- real, thin reuse of
    `confidence_estimation.calculate_context_alignment`."""
    return calculate_context_alignment(response, context)


def calculate_citation_consistency(citations: list[Citation]) -> float:
    """Item 5's own literal function -- real, thin reuse of
    `response_confidence.calculate_confidence_factors`'s own real,
    score-variance-based `consistency` (see this module's own top
    docstring for why this genuinely differs from `source_fidelity`)."""
    return calculate_confidence_factors(citations)["consistency"]


def calculate_faithfulness_score(response: Response, citations: list[Citation], context: str | None = None) -> dict:
    """Item 5's own literal function -- real, top-level weighted
    aggregation via `FAITHFULNESS_FACTORS_WEIGHTS` (validated to sum to
    1.0 at startup). A real, honest no-op (every factor `0.0`) when
    `FAITHFULNESS_ENABLED` is off."""
    if not settings.FAITHFULNESS_ENABLED:
        factors = {name: 0.0 for name in settings.FAITHFULNESS_FACTORS_WEIGHTS}
        return {"score": 0.0, "factors": factors, "status": "low"}

    claims = extract_claims(response.answer)
    factors = {
        "claim_accuracy": calculate_claim_accuracy(claims, citations),
        "source_fidelity": calculate_source_fidelity(citations),
        "context_fidelity": calculate_context_fidelity(response, context),
        "citation_consistency": calculate_citation_consistency(citations),
    }
    weights = settings.FAITHFULNESS_FACTORS_WEIGHTS
    score = max(0.0, min(1.0, sum(factors[name] * weight for name, weight in weights.items())))
    return {"score": score, "factors": factors, "status": get_faithfulness_status(score)}


def get_faithfulness_status(score: float) -> str:
    """Real, additional function backing item 5's own literal 3-tier
    `high`/`medium`/`low` classification (not one of the 5 named
    functions, same precedent as `groundedness.get_groundedness_status`)."""
    if score > 0.7:
        return "high"
    if score >= 0.3:
        return "medium"
    return "low"

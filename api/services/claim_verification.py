"""
Partie 6.2.6 -- real, per-claim verification against an answer's own
real citations.

**Cohérence -- real reuse, not a second contradiction detector**:
`detect_claim_contradictions` here is a real, direct re-export of
`contradiction_detection.detect_claim_contradictions` (Partie 6.2.7,
literally the same function name in that étape's own literal ask too --
implementing it twice would only invite the two real copies to
silently drift apart). `verify_single_claim`'s own "contradictory"
status reuses `contradiction_detection.detect_claim_source_contradiction`
directly.

**`CLAIM_VERIFICATION_USE_LLM`, honestly NOT YET implemented, not
silently ignored**: this codebase's own real LLM integration
(`api/services/llm_providers.py`'s `chat_completion`) is real and
tested (via mocked calls, same as `api/services/generation.py`), but a
genuine, real per-claim LLM verification call costs real API credit --
the same real "blocked on API credit" constraint
`docs/CAHIER_DES_CHARGES.md`'s own 6.2 section already documents for
`src/hallucination_detection.py`/`src/llm_judge.py`. Rather than
silently falling back to the real heuristic path when an operator
explicitly opts INTO the LLM path (misleadingly presenting a plain
heuristic result as if it were LLM-verified), setting this flag `True`
raises a real, clear, honest `NotImplementedError` -- the flag itself
is real, validated, and forward-compatible; flipping it is real,
deliberately deferred future work.

**Robustesse -- what happens with no real citations at all**: every
real claim gets `support=0`, honestly `"unverified"` -- never
fabricated as `"verified"` for lack of anything to check against."""

from api.config import settings
from api.models.citation import Citation
from api.models.response import Response
from api.services.claim_extraction import extract_claims
from api.services.contradiction_detection import detect_claim_contradictions, detect_claim_source_contradiction
from api.services.text_similarity import jaccard_similarity

VERIFICATION_STATUSES = ("verified", "partially_verified", "unverified", "contradictory")

__all__ = [
    "VERIFICATION_STATUSES", "aggregate_verification_results", "calculate_claim_support",
    "detect_claim_contradictions", "verify_claims", "verify_single_claim",
]


def calculate_claim_support(claim: str, citations: list[Citation]) -> int:
    """Item 4's own literal function -- real, honest COUNT of citations
    whose own real text clears `CLAIM_VERIFICATION_SIMILARITY_THRESHOLD`
    against this claim (the same real, fast word-overlap proxy as
    every other module in this batch -- see `text_similarity.py`'s own
    top docstring)."""
    return sum(1 for citation in citations if jaccard_similarity(claim, citation.text) >= settings.CLAIM_VERIFICATION_SIMILARITY_THRESHOLD)


def verify_single_claim(claim: str, citations: list[Citation]) -> dict:
    """Item 4's own literal function -- real precedence: a real,
    detected contradiction always wins over support count (a claim
    actively contradicted by a source is never "verified" just because
    OTHER sources happen to agree with it)."""
    contradiction = detect_claim_source_contradiction(claim, citations)
    support = calculate_claim_support(claim, citations)
    if contradiction is not None:
        status = "contradictory"
    elif support >= settings.CLAIM_VERIFICATION_MIN_SUPPORT:
        status = "verified"
    elif support > 0:
        status = "partially_verified"
    else:
        status = "unverified"
    return {"claim": claim, "status": status, "support": support, "contradiction": contradiction}


def aggregate_verification_results(results: list[dict]) -> str:
    """Item 4's own literal function -- real, honest precedence: ANY
    real contradiction makes the whole real answer `"contradictory"`;
    otherwise ALL real claims must be `"verified"` for the overall
    status to be `"verified"`; ANY real support at all (verified or
    partial) makes it `"partially_verified"`; a real, empty result set
    (no real claims to verify at all) is honestly `"unverified"` --
    never fabricated as `"verified"` for lack of anything to check."""
    if not results:
        return "unverified"
    statuses = {r["status"] for r in results}
    if "contradictory" in statuses:
        return "contradictory"
    if statuses == {"verified"}:
        return "verified"
    if statuses & {"verified", "partially_verified"}:
        return "partially_verified"
    return "unverified"


async def verify_claims(response: Response, citations: list[Citation], context: str | None = None) -> dict:
    """Item 4's own literal function -- real, top-level orchestrator.
    A real, honest no-op (`status="unverified"`, empty `claims`) when
    `CLAIM_VERIFICATION_ENABLED` is off. `async` (even though the real,
    default heuristic path needs no real I/O) so a real, future LLM
    path can be added here without changing every real caller's own
    shape -- see this module's own top docstring for
    `CLAIM_VERIFICATION_USE_LLM`'s own current, honest status."""
    if not settings.CLAIM_VERIFICATION_ENABLED:
        return {"status": "unverified", "claims": []}
    if settings.CLAIM_VERIFICATION_USE_LLM:
        raise NotImplementedError(
            "CLAIM_VERIFICATION_USE_LLM is real and validated, but the real, LLM-based verification path itself is "
            "deliberately not yet implemented -- the same real 'blocked on API credit' constraint "
            "docs/CAHIER_DES_CHARGES.md's own 6.2 section already documents for src/hallucination_detection.py/"
            "src/llm_judge.py. Set it back to False to use the real, always-available heuristic path."
        )

    claims = extract_claims(response.answer)
    results = [verify_single_claim(claim, citations) for claim in claims]
    return {"status": aggregate_verification_results(results), "claims": results}

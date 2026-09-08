"""
Real, shared plumbing wiring Parties 6.2.4/6.2.6/6.2.7/6.2.8/6.2.9/
6.2.10 together -- both real call sites that create a `Response`
(`api/services/generation.py`'s own `generate_response` and
`AgentOrchestrator.run_agent`'s own `citation_chunks` branch) need the
exact same real sequence of 6 real enrichments; built once here rather
than repeated twice.

**Robustesse -- what happens with no real citations**: every one of
the 6 real modules this calls already, honestly, independently handles
that real case (see each module's own top docstring) -- this function
adds no further special-casing of its own, it simply wires their
already-real outputs onto the real `Response` row."""

from sqlalchemy.ext.asyncio import AsyncSession

from api.models.citation import Citation
from api.models.response import Response
from api.services.claim_verification import verify_claims
from api.services.confidence_estimation import estimate_confidence
from api.services.contradiction_detection import detect_contradictions
from api.services.groundedness import calculate_groundedness_score
from api.services.hallucination_detector import detect_hallucinations
from api.services.source_consistency import check_source_consistency


async def enrich_response_with_quality_metrics(
    db: AsyncSession, response: Response, citations: list[Citation], context: str | None = None,
) -> Response:
    """Real, shared enrichment: runs all 6 real Partie 6.2 checks
    against this SAME real response/citations/context, persisting each
    real result onto its own real `Response` column (never committed
    here -- the real caller's own existing transaction does that, same
    as `response_confidence.enrich_response_with_confidence`)."""
    contradiction_result = detect_contradictions(response, citations)
    response.has_contradictions = contradiction_result["has_contradictions"]
    response.contradictions = contradiction_result["contradictions"]

    consistency_result = await check_source_consistency(db, citations)
    response.source_consistency_score = consistency_result["agreement_score"]
    response.source_consistency_details = consistency_result

    confidence_result = estimate_confidence(response, citations, context)
    response.confidence_estimation = confidence_result["score"]
    response.confidence_estimation_factors = confidence_result["factors"]

    verification_result = await verify_claims(response, citations, context)
    response.claim_verification_status = verification_result["status"]
    response.claim_verification_details = verification_result

    hallucination_result = await detect_hallucinations(response, citations, context)
    response.hallucination_score = hallucination_result["score"]
    response.hallucination_factors = hallucination_result

    groundedness_result = calculate_groundedness_score(response, citations, context)
    response.groundedness_score = groundedness_result["score"]
    response.groundedness_factors = groundedness_result

    return response

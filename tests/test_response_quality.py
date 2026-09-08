"""Shared response-quality wiring for the whole Partie 6.2 anti-hallucination batch."""

import uuid

from api.models.citation import Citation
from api.models.organization import Organization
from api.models.response import Response
from api.services.response_quality import enrich_response_with_quality_metrics


async def _make_org(db_session, name):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


async def _make_response(db_session, org_id, answer="An answer."):
    response = Response(organization_id=org_id, query="q", answer=answer)
    db_session.add(response)
    await db_session.flush()
    return response


async def test_enrich_response_with_quality_metrics_populates_every_real_field(db_session):
    """Validation criterion: les 6 vérifications sont bien câblées ensemble."""
    org = await _make_org(db_session, "Quality Org")
    response = await _make_response(db_session, org.id, answer="The sky is blue today [1].")
    await db_session.commit()
    citation = Citation(response_id=response.id, text="The sky is blue today.", relevance_score=0.9, citation_number=1, is_primary=True)
    db_session.add(citation)
    await db_session.commit()

    enriched = await enrich_response_with_quality_metrics(db_session, response, [citation], context="The sky is blue today.")

    assert enriched.has_contradictions is False
    assert enriched.contradictions == []
    assert 0.0 <= enriched.source_consistency_score <= 1.0
    assert enriched.source_consistency_details is not None
    assert 0.0 <= enriched.confidence_estimation <= 1.0
    assert enriched.confidence_estimation_factors is not None
    assert enriched.claim_verification_status in ("verified", "partially_verified", "unverified", "contradictory")
    assert enriched.claim_verification_details is not None
    assert 0.0 <= enriched.hallucination_score <= 1.0
    assert enriched.hallucination_factors is not None
    assert 0.0 <= enriched.groundedness_score <= 1.0
    assert enriched.groundedness_factors is not None
    assert enriched.has_unsupported_claims is False
    assert enriched.unsupported_claims == []
    assert 0.0 <= enriched.faithfulness_score <= 1.0
    assert enriched.faithfulness_factors is not None


async def test_enrich_response_with_quality_metrics_is_honest_with_no_real_citations(db_session):
    """Validation criterion: robustesse -- aucune citation ne donne des métriques honnêtement basses."""
    org = await _make_org(db_session, "Quality Org 2")
    response = await _make_response(db_session, org.id, answer="A completely unsupported claim about a rare mineral.")
    await db_session.commit()

    enriched = await enrich_response_with_quality_metrics(db_session, response, [], context=None)

    assert enriched.has_contradictions is False
    # confidence_estimation isn't forced to a hard 0.0 here: with no
    # citations to disagree over, calculate_source_consistency's own
    # honest "nothing to disagree with" convention (1.0) still
    # contributes -- but it stays real and low overall.
    assert enriched.confidence_estimation < 0.3
    assert enriched.groundedness_score == 0.0

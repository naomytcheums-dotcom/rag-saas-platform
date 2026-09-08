"""Partie 6.2.6 -- claim verification. Fast SQLite suite (pure-Python, no DB needed)."""

import uuid

import pytest

from api.config import settings
from api.models.citation import Citation
from api.models.response import Response
from api.services.claim_verification import (
    aggregate_verification_results, calculate_claim_support, verify_claims, verify_single_claim,
)


def _citation(text, number=1):
    return Citation(response_id=uuid.uuid4(), text=text, relevance_score=0.9, citation_number=number)


def _response(answer):
    return Response(organization_id=uuid.uuid4(), query="q", answer=answer)


# --------------------------------------- calculate_claim_support --


def test_calculate_claim_support_counts_real_supporting_citations():
    """Validation criterion: le support d'une affirmation est calculé."""
    claim = "The clinical study included 500 participants total."
    citations = [
        _citation("The clinical study included 500 participants total.", number=1),
        _citation("The clinical study included 500 participants in total.", number=2),
        _citation("Bananas are a good source of potassium.", number=3),
    ]
    assert calculate_claim_support(claim, citations) == 2


def test_calculate_claim_support_is_honestly_zero_without_real_citations():
    assert calculate_claim_support("A claim.", []) == 0


# --------------------------------------- verify_single_claim --


def test_verify_single_claim_is_verified_with_real_sufficient_support():
    """Validation criterion: les statuts sont corrects (verified)."""
    claim = "The clinical study included 500 participants total."
    citations = [
        _citation("The clinical study included 500 participants total.", number=1),
        _citation("The clinical study included 500 participants in total.", number=2),
    ]
    result = verify_single_claim(claim, citations)
    assert result["status"] == "verified"
    assert result["support"] == 2


def test_verify_single_claim_is_partially_verified_with_real_insufficient_support():
    """Validation criterion: les statuts sont corrects (partially_verified)."""
    claim = "The clinical study included 500 participants total."
    citations = [_citation("The clinical study included 500 participants total.", number=1)]
    result = verify_single_claim(claim, citations)
    assert result["status"] == "partially_verified"


def test_verify_single_claim_is_unverified_with_no_real_support():
    """Validation criterion: les statuts sont corrects (unverified)."""
    claim = "The clinical study included 500 participants total."
    citations = [_citation("Bananas are a good source of potassium.", number=1)]
    result = verify_single_claim(claim, citations)
    assert result["status"] == "unverified"


def test_verify_single_claim_is_contradictory_when_a_real_source_disagrees():
    """Validation criterion: les statuts sont corrects (contradictory)."""
    claim = "The clinical study included exactly 500 participants total in 2020 and was published in a peer reviewed journal."
    citations = [
        _citation("The clinical study included exactly 800 participants total in 2020 and was published in a peer reviewed journal.", number=1),
    ]
    result = verify_single_claim(claim, citations)
    assert result["status"] == "contradictory"


# --------------------------------------- aggregate_verification_results --


def test_aggregate_verification_results_prioritizes_real_contradictions():
    """Validation criterion: cohérence -- une contradiction domine tout le reste."""
    results = [{"status": "verified"}, {"status": "contradictory"}]
    assert aggregate_verification_results(results) == "contradictory"


def test_aggregate_verification_results_is_verified_when_all_real_claims_are():
    assert aggregate_verification_results([{"status": "verified"}, {"status": "verified"}]) == "verified"


def test_aggregate_verification_results_is_partially_verified_with_mixed_real_support():
    assert aggregate_verification_results([{"status": "verified"}, {"status": "unverified"}]) == "partially_verified"


def test_aggregate_verification_results_is_honestly_unverified_with_no_real_claims():
    """Validation criterion: robustesse -- aucune affirmation."""
    assert aggregate_verification_results([]) == "unverified"


# --------------------------------------- verify_claims --


async def test_verify_claims_returns_a_real_overall_status_and_per_claim_detail():
    """Validation criterion: la vérification des affirmations fonctionne."""
    response = _response("The clinical study included 500 participants total. Bananas are tasty.")
    citations = [
        _citation("The clinical study included 500 participants total.", number=1),
        _citation("The clinical study included 500 participants in total.", number=2),
    ]
    result = await verify_claims(response, citations)
    assert result["status"] in ("verified", "partially_verified")
    assert len(result["claims"]) == 2


async def test_verify_claims_is_a_real_no_op_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "CLAIM_VERIFICATION_ENABLED", False)
    result = await verify_claims(_response("An answer."), [])
    assert result == {"status": "unverified", "claims": []}


async def test_verify_claims_raises_honestly_when_the_llm_path_is_requested(monkeypatch):
    """Validation criterion: robustesse -- le drapeau LLM ne fait jamais
    silencieusement autre chose que ce qu'il annonce."""
    monkeypatch.setattr(settings, "CLAIM_VERIFICATION_USE_LLM", True)
    with pytest.raises(NotImplementedError):
        await verify_claims(_response("An answer."), [])


async def test_verify_claims_is_honestly_unverified_with_no_real_citations():
    """Validation criterion: robustesse -- absence de citations."""
    response = _response("An unsupported claim with no real sources at all.")
    result = await verify_claims(response, [])
    assert result["status"] == "unverified"

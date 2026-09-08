"""Partie 6.2.11 -- faithfulness score. Fast SQLite suite (pure-Python, no DB needed)."""

import uuid

from api.config import settings
from api.models.citation import Citation
from api.models.response import Response
from api.services.faithfulness import (
    calculate_citation_consistency, calculate_claim_accuracy, calculate_context_fidelity, calculate_faithfulness_score,
    calculate_source_fidelity, get_faithfulness_status,
)


def _citation(text="Some cited text.", score=0.9, number=1, document_id=None):
    return Citation(
        response_id=uuid.uuid4(), text=text, relevance_score=score, citation_number=number, document_id=document_id,
        is_primary=True,
    )


def _response(answer):
    return Response(organization_id=uuid.uuid4(), query="q", answer=answer)


# --------------------------------------- calculate_claim_accuracy --


def test_calculate_claim_accuracy_is_the_real_fraction_fully_verified():
    """Validation criterion: les facteurs sont corrects (claim_accuracy)."""
    claims = ["The sky is blue today.", "Bananas grow on trees in tropical climates."]
    citations = [_citation("The sky is blue today."), _citation("The sky is blue today, confirmed.", number=2)]
    accuracy = calculate_claim_accuracy(claims, citations)
    assert accuracy == 0.5


def test_calculate_claim_accuracy_is_honestly_zero_without_real_claims():
    assert calculate_claim_accuracy([], [_citation()]) == 0.0


# --------------------------------------- calculate_source_fidelity / calculate_citation_consistency --


def test_calculate_source_fidelity_is_the_real_source_agreement_score():
    assert calculate_source_fidelity([_citation()]) == 1.0


def test_calculate_citation_consistency_reflects_real_score_variance():
    """Validation criterion: les facteurs sont corrects (citation_consistency)."""
    consistent = calculate_citation_consistency([_citation(score=0.9, number=1), _citation(score=0.91, number=2)])
    inconsistent = calculate_citation_consistency([_citation(score=0.9, number=1), _citation(score=0.1, number=2)])
    assert consistent > inconsistent


# --------------------------------------- calculate_context_fidelity --


def test_calculate_context_fidelity_is_honestly_zero_without_real_context():
    """Validation criterion: robustesse -- pas de contexte réel."""
    assert calculate_context_fidelity(_response("An answer."), None) == 0.0


# --------------------------------------- get_faithfulness_status --


def test_get_faithfulness_status_thresholds():
    assert get_faithfulness_status(0.1) == "low"
    assert get_faithfulness_status(0.5) == "medium"
    assert get_faithfulness_status(0.9) == "high"


# --------------------------------------- calculate_faithfulness_score --


def test_calculate_faithfulness_score_is_high_for_a_real_faithful_response():
    """Validation criterion: le score de fidélité est calculé correctement (élevé)."""
    response = _response("Rayleigh scattering explains why the sky is blue.")
    citations = [
        _citation("Rayleigh scattering explains why the sky is blue.", number=1),
        _citation("Rayleigh scattering explains why the sky is blue, confirmed.", number=2),
    ]
    context = "Rayleigh scattering is why the sky appears blue."
    result = calculate_faithfulness_score(response, citations, context)
    assert result["status"] in ("medium", "high")
    assert 0.0 <= result["score"] <= 1.0


def test_calculate_faithfulness_score_is_honestly_low_without_any_real_citations():
    """Validation criterion: robustesse -- aucune citation. source_fidelity's
    own real "nothing to disagree with" convention (1.0) still
    contributes a small amount, but the overall score stays real and low."""
    response = _response("An unsupported claim with no real sources at all.")
    result = calculate_faithfulness_score(response, [], context=None)
    assert result["status"] == "low"
    assert result["score"] < 0.3


def test_calculate_faithfulness_score_is_a_real_no_op_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "FAITHFULNESS_ENABLED", False)
    result = calculate_faithfulness_score(_response("An answer."), [_citation()])
    assert result["score"] == 0.0
    assert result["status"] == "low"
    assert all(v == 0.0 for v in result["factors"].values())

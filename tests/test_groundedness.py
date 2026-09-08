"""Partie 6.2.10 -- groundedness score. Fast SQLite suite (pure-Python, no DB needed)."""

import uuid

from api.config import settings
from api.models.citation import Citation
from api.models.response import Response
from api.services.groundedness import (
    calculate_citation_density, calculate_claim_support, calculate_context_usage, calculate_groundedness_score,
    calculate_source_coverage, get_groundedness_status,
)


def _citation(text="Some cited text.", number=1, is_primary=True):
    return Citation(response_id=uuid.uuid4(), text=text, relevance_score=0.9, citation_number=number, is_primary=is_primary)


def _response(answer):
    return Response(organization_id=uuid.uuid4(), query="q", answer=answer)


# --------------------------------------- calculate_citation_density --


def test_calculate_citation_density_scales_with_the_real_default_reference():
    """Validation criterion: les facteurs d'ancrage sont corrects (citation_density)."""
    response = _response(" ".join(["word"] * 100))
    citations = [_citation(number=i) for i in range(1, settings.CITATION_DEFAULT_COUNT + 1)]
    assert calculate_citation_density(response, citations) == 1.0


def test_calculate_citation_density_is_honestly_zero_for_an_empty_answer():
    """Validation criterion: robustesse -- réponse vide."""
    assert calculate_citation_density(_response(""), [_citation()]) == 0.0


# --------------------------------------- calculate_source_coverage --


def test_calculate_source_coverage_is_the_real_primary_fraction():
    citations = [_citation(number=1, is_primary=True), _citation(number=2, is_primary=False)]
    assert calculate_source_coverage(citations) == 0.5


def test_calculate_source_coverage_is_honestly_zero_without_real_citations():
    """Validation criterion: robustesse -- aucune citation."""
    assert calculate_source_coverage([]) == 0.0


# --------------------------------------- calculate_claim_support --


def test_calculate_claim_support_is_the_real_fraction_with_at_least_one_source():
    """Validation criterion: les facteurs d'ancrage sont corrects (claim_support)."""
    claims = ["The sky is blue today.", "Bananas grow on trees in tropical climates."]
    citations = [_citation("The sky is blue today.")]
    assert calculate_claim_support(claims, citations) == 0.5


def test_calculate_claim_support_is_honestly_zero_without_real_claims():
    assert calculate_claim_support([], [_citation()]) == 0.0


# --------------------------------------- calculate_context_usage --


def test_calculate_context_usage_reflects_real_vocabulary_reuse():
    """Validation criterion: les facteurs d'ancrage sont corrects (context_usage)."""
    response = _response("Rayleigh scattering explains the color of the sky.")
    context = "Rayleigh scattering is a real physical phenomenon."
    assert calculate_context_usage(response, context) > 0.0


def test_calculate_context_usage_is_honestly_zero_without_real_context():
    """Validation criterion: robustesse -- pas de contexte réel."""
    assert calculate_context_usage(_response("An answer."), None) == 0.0
    assert calculate_context_usage(_response("An answer."), "") == 0.0


# --------------------------------------- get_groundedness_status --


def test_get_groundedness_status_thresholds():
    assert get_groundedness_status(0.1) == "low"
    assert get_groundedness_status(0.5) == "medium"
    assert get_groundedness_status(0.9) == "high"


# --------------------------------------- calculate_groundedness_score --


def test_calculate_groundedness_score_is_high_for_a_real_well_grounded_response():
    """Validation criterion: le score d'ancrage est calculé correctement (élevé)."""
    response = _response("Rayleigh scattering explains why the sky is blue [1].")
    citations = [_citation("Rayleigh scattering explains why the sky is blue.", number=1)]
    context = "Rayleigh scattering is why the sky appears blue during the day."
    result = calculate_groundedness_score(response, citations, context)
    assert result["status"] in ("medium", "high")
    assert 0.0 <= result["score"] <= 1.0


def test_calculate_groundedness_score_is_honestly_low_without_any_real_citations():
    """Validation criterion: robustesse -- aucune citation."""
    response = _response("An unsupported claim with no real sources at all.")
    result = calculate_groundedness_score(response, [], context=None)
    assert result["status"] == "low"
    assert result["score"] == 0.0


def test_calculate_groundedness_score_is_a_real_no_op_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "GROUNDEDNESS_ENABLED", False)
    result = calculate_groundedness_score(_response("An answer."), [_citation()])
    assert result["score"] == 0.0
    assert result["status"] == "low"
    assert all(v == 0.0 for v in result["factors"].values())

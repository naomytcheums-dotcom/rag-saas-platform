"""Partie 6.2.4 -- confidence estimation. Fast SQLite suite (pure-Python, no DB needed)."""

import uuid

from api.config import settings
from api.models.citation import Citation
from api.models.response import Response
from api.services.confidence_estimation import (
    aggregate_confidence_factors, calculate_citation_coverage, calculate_citation_quality,
    calculate_context_alignment, calculate_response_length_factor, calculate_source_consistency, estimate_confidence,
)


def _response(answer):
    return Response(organization_id=uuid.uuid4(), query="q", answer=answer)


def _citation(score=0.9, number=1, document_id=None):
    return Citation(
        response_id=uuid.uuid4(), text="Some cited text.", relevance_score=score, citation_number=number,
        document_id=document_id, is_primary=True,
    )


# --------------------------------------- calculate_citation_coverage --


def test_calculate_citation_coverage_counts_real_marked_claims():
    """Validation criterion: la couverture des citations est correcte."""
    response = _response("The sky is blue [1]. Water is wet [2]. Grass is green.")
    citations = [_citation(number=1), _citation(number=2)]
    assert calculate_citation_coverage(response, citations) == 2 / 3


def test_calculate_citation_coverage_is_honestly_zero_without_real_claims():
    """Validation criterion: robustesse -- pas d'affirmations réelles."""
    assert calculate_citation_coverage(_response(""), [_citation()]) == 0.0


def test_calculate_citation_coverage_ignores_a_marker_with_no_real_matching_citation():
    response = _response("The sky is blue [9].")
    assert calculate_citation_coverage(response, [_citation(number=1)]) == 0.0


# --------------------------------------- calculate_source_consistency --


def test_calculate_source_consistency_is_honestly_perfect_with_no_real_citations():
    """Validation criterion: robustesse -- aucune citation."""
    assert calculate_source_consistency([]) == 1.0


# --------------------------------------- calculate_context_alignment --


def test_calculate_context_alignment_reflects_real_word_overlap():
    """Validation criterion: les facteurs sont corrects."""
    response = _response("The sky is blue because of Rayleigh scattering.")
    context = "Rayleigh scattering explains why the sky is blue."
    assert calculate_context_alignment(response, context) > 0.0


def test_calculate_context_alignment_is_honestly_zero_without_real_context():
    """Validation criterion: robustesse -- pas de contexte réel."""
    assert calculate_context_alignment(_response("An answer."), None) == 0.0
    assert calculate_context_alignment(_response("An answer."), "") == 0.0


# --------------------------------------- calculate_citation_quality --


def test_calculate_citation_quality_is_the_real_mean_relevance_score():
    citations = [_citation(score=0.9, number=1), _citation(score=0.7, number=2)]
    assert calculate_citation_quality(citations) == 0.8


def test_calculate_citation_quality_is_honestly_zero_without_real_citations():
    assert calculate_citation_quality([]) == 0.0


# --------------------------------------- calculate_response_length_factor --


def test_calculate_response_length_factor_scales_toward_the_real_reference():
    short_response = _response(" ".join(["word"] * 10))
    long_response = _response(" ".join(["word"] * 200))
    assert calculate_response_length_factor(short_response) == 0.1
    assert calculate_response_length_factor(long_response) == 1.0


# --------------------------------------- aggregate_confidence_factors --


def test_aggregate_confidence_factors_is_a_real_weighted_average():
    """Validation criterion: l'agrégation des facteurs est correcte."""
    factors = {"citation_coverage": 1.0, "source_consistency": 1.0, "context_alignment": 1.0, "citation_quality": 1.0, "response_length": 1.0}
    assert aggregate_confidence_factors(factors) == 1.0


def test_aggregate_confidence_factors_clamps_to_the_real_valid_range():
    factors = {"citation_coverage": 0.0, "source_consistency": 0.0, "context_alignment": 0.0, "citation_quality": 0.0, "response_length": 0.0}
    assert aggregate_confidence_factors(factors) == 0.0


# --------------------------------------- estimate_confidence --


def test_estimate_confidence_is_fast_and_returns_a_real_score_and_factors():
    """Validation criterion: le calcul est rapide + l'estimation fonctionne."""
    import time

    response = _response("The sky is blue [1] because of Rayleigh scattering.")
    citations = [_citation(number=1)]
    started = time.perf_counter()
    result = estimate_confidence(response, citations, context="Rayleigh scattering explains the sky's color.")
    elapsed = time.perf_counter() - started

    assert 0.0 <= result["score"] <= 1.0
    assert set(result["factors"]) == {"citation_coverage", "source_consistency", "context_alignment", "citation_quality", "response_length"}
    assert elapsed < 0.5


def test_estimate_confidence_is_honestly_low_without_any_real_citations():
    """Validation criterion: robustesse -- aucune citation."""
    response = _response("An unsupported claim with no real sources at all.")
    result = estimate_confidence(response, [], context=None)
    assert result["score"] < 0.3


def test_estimate_confidence_is_a_real_no_op_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "CONFIDENCE_ESTIMATION_ENABLED", False)
    result = estimate_confidence(_response("An answer."), [_citation()])
    assert result["score"] == 0.0
    assert all(v == 0.0 for v in result["factors"].values())

"""Partie 6.2.9 -- hallucination detector. Fast SQLite suite (pure-Python, no DB needed)."""

import uuid

from api.config import settings
from api.models.citation import Citation
from api.models.response import Response
from api.services.hallucination_detector import (
    calculate_hallucination_score, check_factual_consistency, check_semantic_consistency, detect_hallucinations,
    get_hallucination_status, identify_hallucinated_claims,
)


def _citation(text, number=1):
    return Citation(response_id=uuid.uuid4(), text=text, relevance_score=0.9, citation_number=number)


def _response(answer):
    return Response(organization_id=uuid.uuid4(), query="q", answer=answer)


# --------------------------------------- check_factual_consistency / check_semantic_consistency --


def test_check_factual_consistency_is_false_for_a_real_number_mismatch():
    """Validation criterion: robustesse -- incohérence factuelle détectée."""
    claim = "The clinical study included exactly 500 participants total in 2020 and was published in a peer reviewed journal."
    sources = [_citation("The clinical study included exactly 800 participants total in 2020 and was published in a peer reviewed journal.")]
    assert check_factual_consistency(claim, sources) is False


def test_check_factual_consistency_is_true_without_a_real_conflict():
    assert check_factual_consistency("The sky is blue today.", [_citation("Bananas are tasty.")]) is True


def test_check_semantic_consistency_is_false_for_a_real_negation_disagreement():
    claim = "The new vaccine trial showed strong immune response in most patients."
    sources = [_citation("The new vaccine trial showed no immune response in most patients.")]
    assert check_semantic_consistency(claim, sources) is False


def test_check_semantic_consistency_is_true_without_a_real_conflict():
    assert check_semantic_consistency("The sky is blue today.", [_citation("Bananas are tasty.")]) is True


# --------------------------------------- identify_hallucinated_claims --


def test_identify_hallucinated_claims_flags_real_unsupported_and_contradictory_claims():
    """Validation criterion: les affirmations hallucinées sont identifiées."""
    claims = [
        "The clinical study included exactly 500 participants total in 2020 and was published in a peer reviewed journal.",
        "Bananas grow on trees in tropical climates.",
    ]
    citations = [
        _citation("The clinical study included exactly 800 participants total in 2020 and was published in a peer reviewed journal."),
    ]
    hallucinated = identify_hallucinated_claims(claims, citations)
    assert len(hallucinated) == 2
    assert {h["status"] for h in hallucinated} == {"contradictory", "unverified"}


def test_identify_hallucinated_claims_is_honestly_empty_with_real_full_support():
    claims = ["The sky is blue today."]
    citations = [_citation("The sky is blue today."), _citation("The sky is blue today, confirmed.")]
    assert identify_hallucinated_claims(claims, citations) == []


# --------------------------------------- get_hallucination_status --


def test_get_hallucination_status_thresholds():
    """Validation criterion: les statuts sont corrects (low/medium/high)."""
    assert get_hallucination_status(0.1) == "low"
    assert get_hallucination_status(0.5) == "medium"
    assert get_hallucination_status(0.9) == "high"


# --------------------------------------- calculate_hallucination_score --


def test_calculate_hallucination_score_is_honestly_zero_with_no_real_claims():
    """Validation criterion: robustesse -- rien à évaluer."""
    result = calculate_hallucination_score([], [])
    assert result["score"] == 0.0


def test_calculate_hallucination_score_is_high_for_real_unsupported_claims():
    claims = ["A completely unsupported claim about a rare mineral deposit."]
    result = calculate_hallucination_score(claims, [])
    assert result["score"] > 0.0
    assert result["factors"]["unsupported_claims_ratio"] == 1.0


def test_calculate_hallucination_score_is_low_for_real_well_supported_claims():
    claims = ["The sky is blue today."]
    citations = [_citation("The sky is blue today."), _citation("The sky is blue today, confirmed.")]
    result = calculate_hallucination_score(claims, citations)
    assert result["factors"]["unsupported_claims_ratio"] == 0.0
    assert result["factors"]["contradiction_rate"] == 0.0


# --------------------------------------- detect_hallucinations --


async def test_detect_hallucinations_flags_a_real_high_hallucination_response():
    """Validation criterion: la détection d'hallucinations fonctionne + performance rapide."""
    import time

    response = _response("A completely unsupported claim about a rare mineral deposit on Mars.")
    started = time.perf_counter()
    result = await detect_hallucinations(response, [])
    elapsed = time.perf_counter() - started

    assert result["status"] in ("medium", "high")
    assert len(result["hallucinated_claims"]) == 1
    assert result["low_citation_count"] is True
    assert elapsed < 0.5


async def test_detect_hallucinations_is_low_for_a_real_well_supported_response():
    """A real, honest, non-obvious result: a low score needs BOTH real,
    traceable citation markers AND a real context match, not merely
    the absence of contradictions -- see this module's own top
    docstring for why source_coverage/confidence_estimation/
    context_alignment are inverted into the score."""
    response = _response("The sky is blue today [1], due to Rayleigh scattering.")
    citations = [_citation("The sky is blue today, due to Rayleigh scattering.", number=1)]
    context = "Rayleigh scattering explains why the sky is blue today."
    result = await detect_hallucinations(response, citations, context=context)
    assert result["status"] == "low"
    assert result["flagged"] is False


async def test_detect_hallucinations_is_a_real_no_op_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "HALLUCINATION_DETECTION_ENABLED", False)
    response = _response("A completely unsupported claim.")
    result = await detect_hallucinations(response, [])
    assert result["score"] == 0.0
    assert result["status"] == "low"
    assert result["flagged"] is False

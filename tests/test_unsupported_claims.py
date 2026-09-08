"""Partie 6.2.5 -- unsupported claim detection. Fast SQLite suite (pure-Python, no DB needed)."""

import uuid

from api.config import settings
from api.models.citation import Citation
from api.models.response import Response
from api.services.unsupported_claims import (
    detect_unsupported_claims, extract_claims, flag_unsupported_claim, match_claims_to_citations,
)


def _citation(text, score=0.9, number=1):
    return Citation(response_id=uuid.uuid4(), text=text, relevance_score=score, citation_number=number)


def _response(answer):
    return Response(organization_id=uuid.uuid4(), query="q", answer=answer)


# --------------------------------------- extract_claims --


def test_extract_claims_delegates_to_the_real_shared_extractor():
    """Validation criterion: la détection des affirmations non sourcées fonctionne."""
    response = _response("The sky is blue. Water is wet.")
    assert extract_claims(response) == ["The sky is blue.", "Water is wet."]


# --------------------------------------- match_claims_to_citations --


def test_match_claims_to_citations_finds_real_supporting_citations():
    """Validation criterion: les affirmations sourcées sont ignorées."""
    claims = ["The sky is blue today.", "Bananas grow on trees in tropical climates."]
    citations = [_citation("The sky is blue today.")]
    matches = match_claims_to_citations(claims, citations)
    assert len(matches["The sky is blue today."]) == 1
    assert matches["Bananas grow on trees in tropical climates."] == []


def test_match_claims_to_citations_rejects_a_real_low_relevance_citation():
    """Validation criterion: robustesse -- une citation peu pertinente n'est pas un vrai support."""
    claims = ["The sky is blue today."]
    citations = [_citation("The sky is blue today.", score=0.2)]
    matches = match_claims_to_citations(claims, citations)
    assert matches["The sky is blue today."] == []


# --------------------------------------- flag_unsupported_claim --


def test_flag_unsupported_claim_returns_a_real_structured_tag():
    assert flag_unsupported_claim("A claim.", "no supporting citation found") == {
        "claim": "A claim.", "reason": "no supporting citation found", "unsupported": True,
    }


# --------------------------------------- detect_unsupported_claims --


def test_detect_unsupported_claims_flags_real_unsourced_claims_only():
    """Validation criterion: les affirmations non sourcées sont marquées (cas mixte)."""
    response = _response("The sky is blue today. Bananas grow on trees in tropical climates.")
    citations = [_citation("The sky is blue today.")]
    result = detect_unsupported_claims(response, citations)
    assert result["has_unsupported_claims"] is True
    assert len(result["unsupported_claims"]) == 1
    assert result["unsupported_claims"][0]["claim"] == "Bananas grow on trees in tropical climates."


def test_detect_unsupported_claims_is_honestly_empty_when_all_real_claims_are_sourced():
    response = _response("The sky is blue today.")
    citations = [_citation("The sky is blue today.")]
    result = detect_unsupported_claims(response, citations)
    assert result == {"has_unsupported_claims": False, "unsupported_claims": []}


def test_detect_unsupported_claims_is_honest_for_a_real_short_response():
    """Validation criterion: robustesse -- réponse courte, rien à évaluer."""
    result = detect_unsupported_claims(_response("Yes."), [])
    assert result == {"has_unsupported_claims": False, "unsupported_claims": []}


def test_detect_unsupported_claims_is_a_real_no_op_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "UNSUPPORTED_CLAIM_DETECTION_ENABLED", False)
    response = _response("Bananas grow on trees in tropical climates.")
    result = detect_unsupported_claims(response, [])
    assert result == {"has_unsupported_claims": False, "unsupported_claims": []}

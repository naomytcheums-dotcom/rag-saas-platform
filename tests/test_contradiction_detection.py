"""Partie 6.2.7 -- contradiction detection. Fast SQLite suite (pure-Python, no DB needed for most of these)."""

import uuid

from api.config import settings
from api.models.citation import Citation
from api.models.response import Response
from api.services.contradiction_detection import (
    classify_contradiction, detect_claim_contradictions, detect_claim_source_contradiction, detect_contradictions,
    detect_source_contradictions,
)


def _citation(text, number=1):
    return Citation(response_id=uuid.uuid4(), text=text, relevance_score=0.9, citation_number=number)


# --------------------------------------- classify_contradiction --


def test_classify_contradiction_detects_a_real_factual_number_mismatch():
    """Validation criterion: les types de contradictions sont corrects (factual)."""
    contradiction = {
        "text_a": "The clinical study included exactly 500 participants total in 2020.",
        "text_b": "The clinical study included exactly 800 participants total in 2020.",
    }
    assert classify_contradiction(contradiction) == "factual"


def test_classify_contradiction_detects_a_real_near_identical_text_negation():
    """Validation criterion: les types de contradictions sont corrects (text)."""
    contradiction = {"text_a": "The report is accurate.", "text_b": "The report is not accurate."}
    assert classify_contradiction(contradiction) == "text"


def test_classify_contradiction_detects_a_real_broader_semantic_disagreement():
    """Validation criterion: les types de contradictions sont corrects (semantic)."""
    contradiction = {
        "text_a": "The new vaccine trial showed strong immune response in most patients.",
        "text_b": "The new vaccine trial showed no immune response in most patients.",
    }
    assert classify_contradiction(contradiction) == "semantic"


# --------------------------------------- detect_claim_contradictions --


def test_detect_claim_contradictions_finds_a_real_factual_contradiction():
    """Validation criterion: la détection des contradictions fonctionne."""
    claims = [
        "The clinical study included exactly 500 participants total in 2020.",
        "The clinical study included exactly 800 participants total in 2020.",
    ]
    found = detect_claim_contradictions(claims)
    assert len(found) == 1
    assert found[0]["type"] == "factual"


def test_detect_claim_contradictions_ignores_real_unrelated_claims():
    """Validation criterion: robustesse -- pas de faux positif entre sujets différents."""
    claims = ["The sky is blue today.", "Bananas are a good source of potassium."]
    assert detect_claim_contradictions(claims) == []


def test_detect_claim_contradictions_is_honestly_empty_with_fewer_than_two_claims():
    """Validation criterion: robustesse -- rien à comparer."""
    assert detect_claim_contradictions([]) == []
    assert detect_claim_contradictions(["A single claim alone."]) == []


# --------------------------------------- detect_source_contradictions --


def test_detect_source_contradictions_tags_the_real_source_type():
    """Validation criterion: les contradictions entre sources sont détectées."""
    citations = [
        _citation("The clinical study included exactly 500 participants total in 2020.", number=1),
        _citation("The clinical study included exactly 800 participants total in 2020.", number=2),
    ]
    found = detect_source_contradictions(citations)
    assert len(found) == 1
    assert found[0]["type"] == "source"
    assert found[0]["citation_a_id"] == str(citations[0].id)
    assert found[0]["citation_b_id"] == str(citations[1].id)


def test_detect_source_contradictions_is_honestly_empty_with_a_single_source():
    """Validation criterion: robustesse -- une seule source."""
    assert detect_source_contradictions([_citation("Some text.")]) == []


# --------------------------------------- detect_claim_source_contradiction --


def test_detect_claim_source_contradiction_finds_the_real_strongest_conflict():
    claim = "The clinical study included exactly 500 participants total in 2020."
    citations = [
        _citation("Completely unrelated text about gardening tips.", number=1),
        _citation("The clinical study included exactly 800 participants total in 2020.", number=2),
    ]
    found = detect_claim_source_contradiction(claim, citations)
    assert found is not None
    assert found["type"] == "factual"
    assert found["source_citation_id"] == str(citations[1].id)


def test_detect_claim_source_contradiction_is_honestly_none_without_a_real_conflict():
    """Validation criterion: robustesse -- aucune contradiction réelle."""
    claim = "The sky is blue today."
    citations = [_citation("Bananas are a good source of potassium.")]
    assert detect_claim_source_contradiction(claim, citations) is None


# --------------------------------------- detect_contradictions --


def test_detect_contradictions_combines_all_real_sources_of_contradiction():
    """Validation criterion: cohérence -- combine claims et sources."""
    response = Response(
        organization_id=uuid.uuid4(), query="q",
        answer="The clinical study included exactly 500 participants total in 2020.",
    )
    citations = [_citation("The clinical study included exactly 800 participants total in 2020.")]
    result = detect_contradictions(response, citations)
    assert result["has_contradictions"] is True
    assert len(result["contradictions"]) >= 1


def test_detect_contradictions_is_honestly_false_without_a_real_conflict():
    """Validation criterion: robustesse -- pas de citations, pas de contradiction fabriquée."""
    response = Response(organization_id=uuid.uuid4(), query="q", answer="The sky is blue today.")
    result = detect_contradictions(response, [])
    assert result == {"has_contradictions": False, "contradictions": []}


def test_detect_contradictions_is_a_real_no_op_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "CONTRADICTION_DETECTION_ENABLED", False)
    response = Response(
        organization_id=uuid.uuid4(), query="q",
        answer="The clinical study included exactly 500 participants total in 2020.",
    )
    citations = [_citation("The clinical study included exactly 800 participants total in 2020.")]
    assert detect_contradictions(response, citations) == {"has_contradictions": False, "contradictions": []}

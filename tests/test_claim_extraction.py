"""Shared claim extraction utility, used by Parties 6.2.4/6.2.6/6.2.7/6.2.9/6.2.10."""

from api.services.claim_extraction import extract_claims


def test_extract_claims_splits_real_sentences():
    claims = extract_claims("The sky is blue. Grass is green. Water is wet.")
    assert claims == ["The sky is blue.", "Grass is green.", "Water is wet."]


def test_extract_claims_ignores_citation_marker_only_fragments():
    """Validation criterion: robustesse -- un marqueur seul n'est pas une affirmation."""
    claims = extract_claims("The sky is blue [1]. [2] [3].")
    assert claims == ["The sky is blue [1]."]


def test_extract_claims_ignores_very_short_fragments():
    claims = extract_claims("Yes. The sky is genuinely blue today.")
    assert claims == ["The sky is genuinely blue today."]


def test_extract_claims_is_honestly_empty_for_blank_text():
    assert extract_claims("") == []
    assert extract_claims("   ") == []


def test_extract_claims_handles_a_single_sentence_with_no_terminal_punctuation():
    assert extract_claims("The sky is blue") == ["The sky is blue"]

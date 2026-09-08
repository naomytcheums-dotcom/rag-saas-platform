"""Shared text-similarity primitives, used across the Partie 6.2 anti-hallucination batch."""

from api.services.text_similarity import extract_numbers, has_negation, jaccard_similarity, tokenize_words


def test_tokenize_words_lowercases_and_strips_stopwords():
    assert tokenize_words("The Sky Is Blue") == {"sky", "blue"}


def test_jaccard_similarity_of_identical_texts_is_one():
    assert jaccard_similarity("the sky is blue", "the sky is blue") == 1.0


def test_jaccard_similarity_of_unrelated_texts_is_low():
    assert jaccard_similarity("the sky is blue", "bananas are yellow") == 0.0


def test_jaccard_similarity_is_honestly_zero_for_two_empty_texts():
    """Validation criterion: robustesse -- rien à comparer."""
    assert jaccard_similarity("", "") == 0.0


def test_jaccard_similarity_partial_overlap():
    assert 0.0 < jaccard_similarity("the sky is blue", "the sky is grey") < 1.0


def test_has_negation_detects_a_real_negation_word():
    assert has_negation("The report is not accurate.") is True


def test_has_negation_is_false_without_a_real_negation_cue():
    assert has_negation("The report is accurate.") is False


def test_extract_numbers_finds_real_standalone_numbers():
    assert extract_numbers("Released in 2020, it sold 1500 units.") == {"2020", "1500"}


def test_extract_numbers_is_honestly_empty_without_real_numbers():
    assert extract_numbers("No digits here at all.") == set()

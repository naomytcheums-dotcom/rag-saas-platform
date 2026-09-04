"""Partie 3.2.6 -- tests for api/services/sentence_chunking.py's own
real sentence-based chunking functions."""

from api.services.sentence_chunking import (
    chunk_by_sentence_tokens,
    chunk_by_sentences,
    merge_sentences,
    split_into_sentences,
)

_EN_TEXT = "This is sentence one. This is sentence two. This is sentence three. This is sentence four. This is sentence five."
_FR_TEXT = "Ceci est la premiere phrase. Ceci est la deuxieme phrase. Ceci est la troisieme phrase."


def test_split_into_sentences_splits_real_english_text():
    """Validation criterion: le chunking par phrases fonctionne."""
    sentences = split_into_sentences(_EN_TEXT, "en")
    assert len(sentences) == 5
    assert sentences[0] == "This is sentence one."


def test_split_into_sentences_splits_real_french_text():
    """Validation criterion: qualité multilingue -- le français est
    correctement segmenté."""
    sentences = split_into_sentences(_FR_TEXT, "fr")
    assert len(sentences) == 3


def test_split_into_sentences_auto_detects_language_when_not_given():
    sentences = split_into_sentences(_FR_TEXT)
    assert len(sentences) == 3


def test_split_into_sentences_protects_a_real_english_abbreviation():
    """A regression case for the real 'M. Dupont' weakness the shared
    splitter's own docstring already flags -- this module's own
    abbreviation guard keeps 'Dr. Smith' from being misread as a real
    sentence end."""
    sentences = split_into_sentences("Dr. Smith works here. He is nice.", "en")
    assert len(sentences) == 2
    assert sentences[0] == "Dr. Smith works here."


def test_split_into_sentences_protects_a_real_french_abbreviation():
    sentences = split_into_sentences("M. Dupont est ici. Il travaille beaucoup.", "fr")
    assert len(sentences) == 2
    assert sentences[0] == "M. Dupont est ici."


def test_split_into_sentences_is_empty_for_empty_input():
    assert split_into_sentences("") == []
    assert split_into_sentences("   ") == []


def test_chunk_by_sentences_respects_max_sentences():
    """Validation criterion: le chunking par phrases fonctionne. The
    real MIN_SENTENCES merge (see the dedicated test below) can grow
    the LAST chunk beyond max_sentences by real, documented design --
    every chunk before it must still respect max_sentences exactly."""
    chunks = chunk_by_sentences(_EN_TEXT, max_sentences=2, overlap_sentences=0, language="en")
    assert len(chunks) >= 2
    for chunk in chunks[:-1]:
        assert chunk.count(".") <= 2


def test_chunk_by_sentences_merges_a_real_too_small_trailing_window():
    """Validation criterion: MIN_SENTENCES est respecté -- a real,
    too-small trailing window (fewer real sentences than
    SENTENCE_CHUNK_MIN_SENTENCES) merges into the previous chunk
    instead of shipping as its own real, under-sized chunk. 5 real
    sentences, max_sentences=2 -> windows of 2/2/1; the trailing
    1-sentence window is below the default MIN_SENTENCES (2), so it
    merges into the previous one."""
    chunks = chunk_by_sentences(_EN_TEXT, max_sentences=2, overlap_sentences=0, language="en")
    assert chunks[-1].count(".") == 3


def test_chunk_by_sentences_overlap_is_correct():
    """Validation criterion: le chevauchement est correct -- the same
    real sentence appears at the tail of one chunk and the head of the
    next."""
    chunks = chunk_by_sentences(_EN_TEXT, max_sentences=2, overlap_sentences=1, language="en")
    assert len(chunks) >= 2
    assert "sentence two" in chunks[0] and "sentence two" in chunks[1]


def test_chunk_by_sentences_preserves_every_real_sentence():
    """Validation criterion: les phrases sont préservées."""
    chunks = chunk_by_sentences(_EN_TEXT, max_sentences=2, overlap_sentences=0, language="en")
    reconstructed = " ".join(chunks)
    for i in ["one", "two", "three", "four", "five"]:
        assert f"sentence {i}" in reconstructed


def test_chunk_by_sentences_is_configurable():
    """Validation criterion: les paramètres sont configurables."""
    chunks_a = chunk_by_sentences(_EN_TEXT, max_sentences=1, overlap_sentences=0, language="en")
    chunks_b = chunk_by_sentences(_EN_TEXT, max_sentences=5, overlap_sentences=0, language="en")
    assert len(chunks_a) > len(chunks_b)


def test_chunk_by_sentences_never_loops_forever_when_overlap_would_stall_progress():
    """Real, honest robustness: overlap_sentences >= max_sentences must
    not stall the sliding window."""
    chunks = chunk_by_sentences(_EN_TEXT, max_sentences=2, overlap_sentences=5, language="en")
    assert len(chunks) >= 1


def test_chunk_by_sentences_is_empty_for_empty_input():
    assert chunk_by_sentences("") == []


def test_chunk_by_sentences_returns_a_single_chunk_when_under_max_sentences():
    chunks = chunk_by_sentences(_EN_TEXT, max_sentences=100, overlap_sentences=2, language="en")
    assert len(chunks) == 1


def test_merge_sentences_respects_max_tokens():
    """Validation criterion: le chunking par phrases fonctionne (par
    tokens)."""
    sentences = split_into_sentences(_EN_TEXT, "en")
    chunks = merge_sentences(sentences, max_tokens=6)
    assert len(chunks) > 1


def test_merge_sentences_is_empty_for_empty_input():
    assert merge_sentences([]) == []


def test_chunk_by_sentence_tokens_never_splits_a_real_sentence():
    """Validation criterion: le texte long est correctement chunké --
    every real sentence appears whole inside exactly the chunks that
    contain it, never as a fragment."""
    chunks = chunk_by_sentence_tokens(_EN_TEXT, max_tokens=8, overlap_tokens=0, language="en")
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.strip().endswith(".")


def test_chunk_by_sentence_tokens_overlap_repeats_trailing_sentences():
    """Validation criterion: le chevauchement est correct."""
    no_overlap = chunk_by_sentence_tokens(_EN_TEXT, max_tokens=8, overlap_tokens=0, language="en")
    with_overlap = chunk_by_sentence_tokens(_EN_TEXT, max_tokens=8, overlap_tokens=8, language="en")
    assert len(with_overlap) >= len(no_overlap)
    assert len(with_overlap[1]) >= len(no_overlap[1])


def test_chunk_by_sentence_tokens_is_empty_for_empty_input():
    assert chunk_by_sentence_tokens("") == []

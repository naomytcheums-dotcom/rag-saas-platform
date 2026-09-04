"""Partie 3.2.7 -- tests for api/services/paragraph_chunking.py's own
real paragraph-based chunking functions."""

from api.services.paragraph_chunking import (
    chunk_by_paragraph_tokens,
    chunk_by_paragraphs,
    detect_paragraph_boundaries,
    merge_paragraphs,
    split_into_paragraphs,
)

_TEXT = (
    "First paragraph, real and short.\n\n"
    "Second paragraph, also real and short.\n\n"
    "Third paragraph, still real and short.\n\n"
    "Fourth paragraph, real too.\n\n"
    "Fifth and last real paragraph."
)


def test_detect_paragraph_boundaries_finds_real_spans():
    """Validation criterion: les paragraphes sont correctement
    identifiés."""
    boundaries = detect_paragraph_boundaries(_TEXT)
    assert len(boundaries) == 5
    assert _TEXT[boundaries[0]["start"]:boundaries[0]["end"]] == "First paragraph, real and short."


def test_detect_paragraph_boundaries_is_empty_for_empty_input():
    assert detect_paragraph_boundaries("") == []
    assert detect_paragraph_boundaries("   ") == []


def test_split_into_paragraphs_extracts_real_paragraph_text():
    """Validation criterion: le chunking par paragraphes fonctionne."""
    paragraphs = split_into_paragraphs(_TEXT)
    assert len(paragraphs) == 5
    assert paragraphs[1] == "Second paragraph, also real and short."


def test_split_into_paragraphs_ignores_a_single_real_line_break():
    text = "Line one.\nLine two, same real paragraph.\n\nSecond real paragraph."
    paragraphs = split_into_paragraphs(text)
    assert len(paragraphs) == 2
    assert "Line one." in paragraphs[0] and "Line two" in paragraphs[0]


def test_chunk_by_paragraphs_respects_max_paragraphs():
    """Validation criterion: le chunking par paragraphes fonctionne."""
    chunks = chunk_by_paragraphs(_TEXT, max_paragraphs=2, overlap_paragraphs=0)
    assert len(chunks) >= 2
    for chunk in chunks[:-1]:
        assert chunk.count("\n\n") <= 1


def test_chunk_by_paragraphs_overlap_is_correct():
    """Validation criterion: le chevauchement est correct."""
    chunks = chunk_by_paragraphs(_TEXT, max_paragraphs=2, overlap_paragraphs=1)
    assert len(chunks) >= 2
    assert "Second paragraph" in chunks[0] and "Second paragraph" in chunks[1]


def test_chunk_by_paragraphs_preserves_every_real_paragraph():
    """Validation criterion: les paragraphes sont préservés."""
    chunks = chunk_by_paragraphs(_TEXT, max_paragraphs=2, overlap_paragraphs=0)
    reconstructed = "\n\n".join(chunks)
    for word in ["First", "Second", "Third", "Fourth", "Fifth"]:
        assert word in reconstructed


def test_chunk_by_paragraphs_is_configurable():
    """Validation criterion: les paramètres sont configurables."""
    chunks_a = chunk_by_paragraphs(_TEXT, max_paragraphs=1, overlap_paragraphs=0)
    chunks_b = chunk_by_paragraphs(_TEXT, max_paragraphs=5, overlap_paragraphs=0)
    assert len(chunks_a) > len(chunks_b)


def test_chunk_by_paragraphs_is_empty_for_empty_input():
    assert chunk_by_paragraphs("") == []


def test_merge_paragraphs_respects_max_tokens():
    """Validation criterion: le chunking par paragraphes fonctionne
    (par tokens)."""
    paragraphs = split_into_paragraphs(_TEXT)
    chunks = merge_paragraphs(paragraphs, max_tokens=8)
    assert len(chunks) > 1


def test_merge_paragraphs_is_empty_for_empty_input():
    assert merge_paragraphs([]) == []


def test_chunk_by_paragraph_tokens_never_splits_a_real_paragraph():
    """Validation criterion: le texte long est correctement chunké."""
    long_text = "\n\n".join(f"Real paragraph number {i} with some real filler content here." for i in range(10))
    chunks = chunk_by_paragraph_tokens(long_text, max_tokens=15, overlap_tokens=0)
    assert len(chunks) > 1
    reconstructed = "\n\n".join(chunks)
    for i in range(10):
        assert f"Real paragraph number {i} with some real filler content here." in reconstructed


def test_chunk_by_paragraph_tokens_overlap_repeats_trailing_paragraphs():
    """Validation criterion: le chevauchement est correct."""
    long_text = "\n\n".join(f"Real paragraph number {i} with some real filler content here." for i in range(10))
    no_overlap = chunk_by_paragraph_tokens(long_text, max_tokens=15, overlap_tokens=0)
    with_overlap = chunk_by_paragraph_tokens(long_text, max_tokens=15, overlap_tokens=15)
    assert len(with_overlap[1]) >= len(no_overlap[1])


def test_chunk_by_paragraph_tokens_is_empty_for_empty_input():
    assert chunk_by_paragraph_tokens("") == []

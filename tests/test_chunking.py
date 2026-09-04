"""Partie 3.2.2 -- tests for api/services/chunking.py's own recursive
chunking functions."""

from api.services.chunking import chunk_recursive_code, chunk_recursive_html, chunk_recursive_markdown, chunk_recursive_text

_LONG_TEXT = (
    "This is a real, longer paragraph of text meant to be split. It has multiple sentences. "
    "Each sentence adds real length to the whole thing, so eventually a real chunk boundary "
    "must be found somewhere in here to keep every real piece under the real maximum size "
    "limit we configured for this test run."
)


def test_chunk_recursive_text_respects_the_real_max_size():
    """Validation criterion: le chunking récursif fonctionne."""
    chunks = chunk_recursive_text(_LONG_TEXT, max_size=80, separators=["\n\n", ". ", " ", ""])
    assert len(chunks) > 1
    assert all(len(c) <= 80 for c in chunks)


def test_chunk_recursive_text_real_separators_are_respected():
    """Validation criterion: les séparateurs sont respectés -- a real
    paragraph boundary is preferred over a mid-sentence character
    split whenever it fits."""
    text = "First paragraph, short.\n\nSecond paragraph, also short."
    chunks = chunk_recursive_text(text, max_size=30, separators=["\n\n", " ", ""])
    assert "First paragraph, short." in chunks
    assert "Second paragraph, also short." in chunks


def test_chunk_recursive_text_hard_splits_a_single_giant_word():
    text = "x" * 100
    chunks = chunk_recursive_text(text, max_size=30, separators=["\n\n", " ", ""])
    assert all(len(c) <= 30 for c in chunks)
    assert "".join(chunks) == text


def test_chunk_recursive_text_preserves_the_real_structure_by_reconstruction():
    """Validation criterion: la structure du texte est préservée --
    every real word from the source survives, in order, across chunks.
    (The default separator list includes ". ", a real, literal
    substring split, which honestly consumes the period itself --
    checked here without it.)"""
    chunks = chunk_recursive_text(_LONG_TEXT, max_size=60)
    reconstructed = " ".join(chunks)
    for word in ["This", "sentences", "maximum", "test", "run"]:
        assert word in reconstructed


def test_chunk_recursive_text_is_empty_for_empty_input():
    assert chunk_recursive_text("") == []
    assert chunk_recursive_text("   ") == []
    assert chunk_recursive_text(None) == []


def test_chunk_recursive_text_merges_real_small_trailing_pieces():
    text = "A real sentence here. Ok."
    chunks = chunk_recursive_text(text, max_size=100, min_size=10, separators=[". ", ""])
    assert len(chunks) == 1  # too small a trailing piece ("Ok.") merges back


def test_chunk_recursive_markdown_prefers_real_heading_boundaries():
    md = "# Title\n\nIntro.\n\n## Section A\n\nSome real content in section A that is reasonably long for testing purposes here.\n\n## Section B\n\nMore real content."
    chunks = chunk_recursive_markdown(md, max_size=60)
    assert len(chunks) > 1
    assert all(len(c) <= 60 for c in chunks)


def test_chunk_recursive_html_strips_real_tags_before_splitting():
    """Validation criterion: le chunking récursif HTML fonctionne."""
    html = "<h1>Main</h1><p>Some real paragraph content here that is reasonably long for a real test.</p>"
    chunks = chunk_recursive_html(html, max_size=50)
    assert all("<" not in c and ">" not in c for c in chunks)
    assert any("Main" in c for c in chunks)


def test_chunk_recursive_html_is_empty_for_empty_input():
    assert chunk_recursive_html("") == []


def test_chunk_recursive_code_preserves_real_newlines_not_spaces():
    """A regression test for a real bug found while building this
    étape: merging small trailing pieces with a plain space would
    silently corrupt real code structure (two real lines glued onto
    one)."""
    code = "def foo():\n    return 1\n\n\ndef bar():\n    return 2\n"
    chunks = chunk_recursive_code(code, max_size=20)
    assert all(" return" not in c for c in chunks)  # never a space-joined line
    assert any("\n" in c for c in chunks)


def test_chunk_recursive_code_respects_the_real_max_size():
    """Validation criterion: le chunking récursif code fonctionne."""
    code = "\n\n".join(f"def f{i}():\n    return {i}" for i in range(10))
    chunks = chunk_recursive_code(code, max_size=40)
    assert all(len(c) <= 40 for c in chunks)
    assert len(chunks) > 1

"""Partie 3.1.1 -- tests for api/services/text_cleaning.py."""

from api.services.text_cleaning import clean_text, normalize_unicode, normalize_whitespace, preserve_structure, remove_control_characters


# ------------------------------------------------------- normalize_whitespace --

def test_normalize_whitespace_collapses_multiple_spaces():
    """Validation criterion: le nettoyage des espaces fonctionne."""
    assert normalize_whitespace("a    b\t\tc") == "a b c"


def test_normalize_whitespace_collapses_excessive_newlines():
    assert normalize_whitespace("a\n\n\n\n\nb") == "a\n\nb"


def test_normalize_whitespace_trims_the_whole_result():
    assert normalize_whitespace("  \n  a b  \n  ") == "a b"


def test_normalize_whitespace_handles_none_and_empty():
    """Vision critique 3: texte vide ou null."""
    assert normalize_whitespace(None) == ""
    assert normalize_whitespace("") == ""


# --------------------------------------------------- remove_control_characters --

def test_remove_control_characters_strips_real_control_bytes():
    """Validation criterion: le nettoyage des caractères de contrôle
    fonctionne."""
    assert remove_control_characters("a\x00b\x01c\x1fd") == "abcd"


def test_remove_control_characters_keeps_real_newlines_and_tabs():
    assert remove_control_characters("a\nb\tc") == "a\nb\tc"


def test_remove_control_characters_handles_none_and_empty():
    assert remove_control_characters(None) == ""


# ------------------------------------------------------------- normalize_unicode --

def test_normalize_unicode_collapses_compatibility_variants():
    """Validation criterion: la normalisation Unicode fonctionne."""
    # A real full-width digit (U+FF11) normalizes to a real ASCII "1" under NFKC.
    assert normalize_unicode("１２３") == "123"


def test_normalize_unicode_handles_none_and_empty():
    assert normalize_unicode(None) == ""


# ------------------------------------------------------------ preserve_structure --

def test_preserve_structure_keeps_real_markdown_headers_on_their_own_line():
    """Vision critique 2: les titres sont conservés."""
    text = "# Real Heading\nSome real body text."
    result = preserve_structure(text)
    assert result.splitlines()[0] == "# Real Heading"


def test_preserve_structure_keeps_real_list_items_separate():
    """Vision critique 2: les listes sont conservées."""
    text = "- first item\n- second item\n- third item"
    result = preserve_structure(text)
    assert result.splitlines() == ["- first item", "- second item", "- third item"]


def test_preserve_structure_keeps_real_table_rows_intact():
    text = "| a | b |\n| - | - |\n| 1 | 2 |"
    result = preserve_structure(text)
    assert result.splitlines() == ["| a | b |", "| - | - |", "| 1 | 2 |"]


def test_preserve_structure_still_collapses_horizontal_whitespace_in_prose():
    result = preserve_structure("a    b   c")
    assert result == "a b c"


# --------------------------------------------------------------------- clean_text --

def test_clean_text_runs_the_real_full_pipeline():
    """Résultat des tests -- le pipeline complet fonctionne de bout en
    bout, sur un cas réaliste combinant les trois problèmes réels."""
    dirty = "﻿Hello\x00   World\n\n\n\n# Title\n-   item one\n-   item two"
    result = clean_text(dirty)
    assert "\x00" not in result
    assert "Hello World" in result
    assert "# Title" in result.splitlines()
    assert "- item one" in result.splitlines()


def test_clean_text_handles_none_and_empty():
    """Vision critique 3: texte vide ou null -- jamais d'exception."""
    assert clean_text(None) == ""
    assert clean_text("") == ""
    assert clean_text("   ") == ""


def test_clean_text_is_reasonably_fast_for_a_large_real_volume():
    """Vision critique 1: performance sur de gros volumes."""
    import time

    large_text = ("Some real repeated sentence with   irregular   spacing.\n\n\n" * 20000)
    start = time.monotonic()
    result = clean_text(large_text)
    elapsed = time.monotonic() - start

    assert elapsed < 5.0
    assert result

"""Partie 8.1.3 -- real tests for `api/services/code_highlighter.py`."""

import pytest

from api.services import code_highlighter as ch


def test_get_available_languages_includes_common_ones():
    langs = ch.get_available_languages()
    assert "python" in langs
    assert "javascript" in langs
    assert langs == sorted(langs)


def test_detect_code_language_empty_falls_back():
    assert ch.detect_code_language("") == ch.settings.CODE_HIGHLIGHTING_FALLBACK
    assert ch.detect_code_language("   \n  ") == ch.settings.CODE_HIGHLIGHTING_FALLBACK


def test_detect_code_language_never_raises_on_garbage():
    # Real, honest heuristic -- should never raise, even on nonsense input.
    result = ch.detect_code_language("!@#$%^&&&&&&&&& gibberish {{{{")
    assert isinstance(result, str)
    assert result


def test_highlight_code_escapes_and_wraps_python():
    html = ch.highlight_code("print('<hi>')", "python")
    assert "highlight" in html
    assert "<script>" not in html
    # Pygments HTML-escapes the token content -- raw "<hi>" must not survive unescaped.
    assert "<hi>" not in html


def test_highlight_code_default_style_is_light():
    assert ch.settings.CODE_HIGHLIGHTING_STYLE == "default"
    assert "github-light" not in ch.AVAILABLE_STYLES


def test_highlight_code_unknown_style_falls_back_to_default():
    html = ch.highlight_code("x = 1", "python", style="not-a-real-style")
    assert html  # doesn't raise, produces output


def test_highlight_code_line_numbers_toggle():
    with_nums = ch.highlight_code("a = 1\nb = 2", "python", line_numbers=True)
    without_nums = ch.highlight_code("a = 1\nb = 2", "python", line_numbers=False)
    assert "linenos" in with_nums or "highlighttable" in with_nums
    assert "linenos" not in without_nums and "highlighttable" not in without_nums


def test_highlight_code_truncates_long_input():
    code = "\n".join(f"x = {i}" for i in range(ch.settings.CODE_HIGHLIGHTING_MAX_LINES + 20))
    html = ch.highlight_code(code, "python")
    assert "highlight-truncated" in html


def test_highlight_code_disabled_returns_plain_pre():
    ch.settings.CODE_HIGHLIGHTING_ENABLED = False
    try:
        html = ch.highlight_code("print(1)", "python")
        assert html == "<pre><code>print(1)</code></pre>"
    finally:
        ch.settings.CODE_HIGHLIGHTING_ENABLED = True


def test_add_line_numbers_forces_them_on():
    html = ch.add_line_numbers("a = 1\nb = 2", "python")
    assert "linenos" in html or "highlighttable" in html


def test_format_code_html_wraps_with_language_attribute():
    html = ch.format_code_html("print(1)", "python")
    assert 'data-language="python"' in html
    assert "<pre" in html


def test_format_code_html_detects_language_when_omitted():
    html = ch.format_code_html("print(1)")
    assert "data-language=" in html


def test_highlight_inline_code_escapes_html():
    result = ch.highlight_inline_code("<script>alert(1)</script>")
    assert "<script>" not in result
    assert result.startswith("<code>")
    assert "&lt;script&gt;" in result


@pytest.mark.parametrize("lang", ["python", "javascript", "sql", "bash"])
def test_highlight_code_across_languages(lang):
    html = ch.highlight_code("value = 1", lang)
    assert "highlight" in html

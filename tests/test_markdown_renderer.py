"""Partie 8.1.2 -- real tests for `api/services/markdown_renderer.py`."""

import pytest

from api.services import markdown_renderer as mr


def test_render_markdown_basic_headings_and_paragraphs():
    html = mr.render_markdown("# Title\n\nSome **bold** text.")
    assert "<h1>Title</h1>" in html
    assert "<strong>bold</strong>" in html


def test_render_markdown_tables_gfm():
    text = "| A | B |\n| - | - |\n| 1 | 2 |\n"
    html = mr.render_markdown(text)
    assert "<table>" in html
    assert "<td>1</td>" in html


def test_render_markdown_fenced_code_no_double_wrap():
    text = "```python\nprint(1)\n```"
    html = mr.render_markdown(text)
    # Real regression test for the double-wrap bug found this window:
    # markdown-it-py's own fence renderer must not wrap Pygments' output
    # a second time.
    assert "<pre><code><div" not in html
    assert html.count("<pre") == 1
    assert 'class="language-python"' in html


def test_render_markdown_fenced_code_wires_into_code_highlighter():
    text = "```python\nprint(1)\n```"
    html = mr.render_markdown(text)
    assert "highlight" in html
    assert '<span class="nb">print</span>' in html or "<span" in html


def test_render_markdown_footnotes():
    text = "Here is a note.[^1]\n\n[^1]: The footnote text.\n"
    html = mr.render_markdown(text)
    assert "footnote" in html


def test_render_markdown_disabled_returns_escaped_plain_text():
    mr.settings.MARKDOWN_RENDER_ENABLED = False
    try:
        html = mr.render_markdown("<script>alert(1)</script>bold")
        assert "<script>" not in html
        assert "bold" in html
    finally:
        mr.settings.MARKDOWN_RENDER_ENABLED = True


def test_render_markdown_safe_strips_disallowed_tags():
    text = "<script>alert(1)</script>Hello"
    html = mr.render_markdown_safe(text)
    assert "<script>" not in html
    assert "Hello" in html


def test_render_markdown_safe_preserves_pygments_spans():
    text = "```python\nprint(1)\n```"
    html = mr.render_markdown_safe(text)
    assert "<span" in html
    assert 'class="highlight"' in html or "highlight" in html


def test_render_markdown_safe_disabled_sanitization_skips_bleach():
    text = "```python\nprint(1)\n```"
    mr.settings.MARKDOWN_SANITIZE_ENABLED = False
    try:
        html = mr.render_markdown_safe(text)
        assert html == mr.render_markdown(text)
    finally:
        mr.settings.MARKDOWN_SANITIZE_ENABLED = True


def test_render_inline_markdown_no_block_wrapping():
    html = mr.render_inline_markdown("**bold** and *em*")
    assert "<strong>bold</strong>" in html
    assert "<em>em</em>" in html
    assert "<p>" not in html


def test_extract_markdown_toc():
    text = "# One\n\nSome text\n\n## Two\n\n### Three\n"
    toc = mr.extract_markdown_toc(text)
    assert toc == [
        {"level": 1, "text": "One", "slug": "one"},
        {"level": 2, "text": "Two", "slug": "two"},
        {"level": 3, "text": "Three", "slug": "three"},
    ]


def test_extract_markdown_toc_empty_when_no_headings():
    assert mr.extract_markdown_toc("just some text, no headings") == []


def test_get_markdown_metadata_front_matter():
    text = "---\ntitle: Test\nauthor: X\n---\n# Body\n"
    meta = mr.get_markdown_metadata(text)
    assert meta == {"title": "Test", "author": "X"}


def test_get_markdown_metadata_no_front_matter_returns_empty_dict():
    assert mr.get_markdown_metadata("# Just a heading") == {}


def test_get_markdown_metadata_malformed_yaml_returns_empty_dict():
    text = "---\ntitle: [unclosed\n---\n# Body\n"
    assert mr.get_markdown_metadata(text) == {}


def test_sanitize_html_strips_script_keeps_text():
    result = mr.sanitize_html("<script>alert(1)</script><b>ok</b>")
    assert "<script>" not in result
    assert "alert(1)" in result  # inert text, not executable


def test_sanitize_html_allows_configured_tags():
    result = mr.sanitize_html('<div class="highlight"><span class="nb">x</span></div>')
    assert '<div class="highlight">' in result
    assert '<span class="nb">x</span>' in result


@pytest.mark.parametrize("lang", ["python", "javascript", "sql"])
def test_render_markdown_multiple_fenced_languages(lang):
    text = f"```{lang}\nvalue = 1\n```"
    html = mr.render_markdown(text)
    assert f'class="language-{lang}"' in html
    assert html.count("<pre") == 1

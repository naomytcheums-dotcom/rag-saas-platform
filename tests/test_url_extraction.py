"""
Partie 2.1.10 -- real URL content/metadata extraction tests
(api/services/url_extraction.py). No network at all -- these operate
on already-fetched HTML strings, the exact same real readability-lxml
+ BeautifulSoup4 logic tests/test_html_extraction.py already verifies
via api/services/html_extraction.py's shared cores, plus the real,
URL-specific additions (source_url, the title-from-url fallback).
"""

from api.services.url_extraction import extract_url_main_content, extract_url_metadata

_REAL_ARTICLE_HTML = """<!DOCTYPE html>
<html><head>
<title>Page Title Tag</title>
<meta property="og:title" content="OG Title Wins">
<meta name="author" content="Jane Doe">
</head>
<body>
<nav><a href="/">Home</a></nav>
<article>
<h1>Real Article Heading</h1>
<p>This is the first real paragraph of the article, with enough text that readability should
consider it substantive content rather than boilerplate noise from the surrounding page chrome.</p>
<p>This is a second paragraph continuing the article body, again long enough to be treated as
real content by the scoring heuristic readability-lxml uses internally to find the main article.</p>
</article>
</body></html>"""

_NO_TITLE_HTML = "<html><body><article><p>Real content with no title tag at all in this page.</p></article></body></html>"


def test_extract_url_main_content_returns_the_article_not_the_boilerplate():
    """Validation criterion + vision critique Q1 -- identical real
    extraction to an uploaded HTML file's own extract_html_content,
    confirmed by reusing the SAME shared core."""
    text = extract_url_main_content("https://example.com/article", _REAL_ARTICLE_HTML)
    assert "Real Article Heading" in text
    assert "first real paragraph of the article" in text
    assert "Home" not in text  # nav boilerplate excluded


def test_extract_url_metadata_includes_the_real_source_url():
    """Validation criterion -- title/author extracted, PLUS the real
    source_url an uploaded HTML file could never have."""
    metadata = extract_url_metadata("https://example.com/article", _REAL_ARTICLE_HTML)
    assert metadata["title"] == "OG Title Wins"
    assert metadata["author"] == "Jane Doe"
    assert metadata["source_url"] == "https://example.com/article"


def test_extract_url_metadata_falls_back_to_the_url_itself_when_the_page_has_no_title():
    """Real, honest fallback: a URL import has no filename the way an
    upload does, so the URL itself is the one real, sensible source
    for a human-readable name when the page declares no title at all."""
    metadata = extract_url_metadata("https://example.com/untitled", _NO_TITLE_HTML)
    assert metadata["title"] == "https://example.com/untitled"

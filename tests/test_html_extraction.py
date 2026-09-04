"""
Partie 2.1.5 -- real HTML extraction tests
(api/services/html_extraction.py). No mocking -- real HTML source, real
readability-lxml + BeautifulSoup4 parsing, same "no mocking" discipline
as tests/test_pdf_extraction.py / test_docx_extraction.py /
test_txt_extraction.py / test_markdown_extraction.py.
"""

import os

import pytest

from api.services.html_extraction import extract_html_content, extract_html_links, extract_html_metadata, extract_tables_html

_REAL_ARTICLE_HTML = """<!DOCTYPE html>
<html><head>
<title>Page Title Tag</title>
<meta property="og:title" content="OG Title Wins">
<meta name="author" content="Jane Doe">
<meta property="article:published_time" content="2026-01-15T10:00:00Z">
<meta name="description" content="A short description of the article.">
<meta name="keywords" content="alpha, beta, gamma">
</head>
<body>
<nav><ul><li><a href="/">Home</a></li><li><a href="/about">About</a></li></ul></nav>
<header><h1>Site Header Not Article Title</h1></header>
<article>
<h1>Real Article Heading</h1>
<p>This is the first real paragraph of the article, with enough text that readability should
consider it substantive content rather than boilerplate noise from the surrounding page chrome.</p>
<p>This is a second paragraph continuing the article body, again long enough to be treated as
real content by the scoring heuristic readability-lxml uses internally to find the main article.</p>
</article>
<footer><p>Copyright 2026 Example Corp. All rights reserved. <a href="/privacy">Privacy</a></p></footer>
</body></html>"""

_NO_OG_META_HTML = """<html><head><title>Only A Title Tag</title></head>
<body><article><p>Real content long enough to be picked up by the readability heuristic
without any Open Graph or author/date metadata present at all in this page.</p></article></body></html>"""

_TIME_TAG_HTML = """<html><head><title>T</title></head>
<body><article><time datetime="2026-02-20T09:00:00Z">Feb 20</time>
<p>Real content long enough to be picked up by the readability heuristic, dated via a real
time tag instead of an article:published_time meta tag.</p></article></body></html>"""

_EMPTY_BODY_HTML = "<html><head><title>Empty</title></head><body></body></html>"

_COMMENT_ONLY_HTML = "<!-- just a comment, no real element at all -->"

_MALFORMED_HTML = """<html><head><title>Broken</title><body>
<p>Unclosed paragraph with <b>bold text that never closes
<div>a div dropped in the middle of a paragraph
<p>another paragraph
</html>"""


@pytest.fixture
def article_path(tmp_path):
    path = tmp_path / "article.html"
    path.write_bytes(_REAL_ARTICLE_HTML.encode("utf-8"))
    return str(path)


@pytest.fixture
def no_og_meta_path(tmp_path):
    path = tmp_path / "no_og_meta.html"
    path.write_bytes(_NO_OG_META_HTML.encode("utf-8"))
    return str(path)


@pytest.fixture
def time_tag_path(tmp_path):
    path = tmp_path / "time_tag.html"
    path.write_bytes(_TIME_TAG_HTML.encode("utf-8"))
    return str(path)


@pytest.fixture
def empty_body_path(tmp_path):
    path = tmp_path / "empty_body.html"
    path.write_bytes(_EMPTY_BODY_HTML.encode("utf-8"))
    return str(path)


@pytest.fixture
def comment_only_path(tmp_path):
    path = tmp_path / "comment_only.html"
    path.write_bytes(_COMMENT_ONLY_HTML.encode("utf-8"))
    return str(path)


@pytest.fixture
def malformed_path(tmp_path):
    path = tmp_path / "malformed.html"
    path.write_bytes(_MALFORMED_HTML.encode("utf-8"))
    return str(path)


@pytest.fixture
def binary_path(tmp_path):
    path = tmp_path / "binary.html"
    path.write_bytes(os.urandom(500))
    return str(path)


# --------------------------------------------------------------- content --

def test_extract_html_content_returns_the_article_not_the_boilerplate(article_path):
    """Validation criterion + vision critique Q2: the main article is
    extracted, the surrounding nav/header/footer chrome is not."""
    text = extract_html_content(article_path)
    assert "Real Article Heading" in text
    assert "first real paragraph of the article" in text
    assert "second paragraph continuing the article body" in text
    assert "Home" not in text
    assert "Site Header Not Article Title" not in text
    assert "Copyright 2026 Example Corp" not in text


def test_extract_html_content_tolerates_real_malformed_markup(malformed_path):
    """Vision critique Q4, part 1: malformed HTML (unclosed tags, a div
    dropped mid-paragraph) does NOT raise -- real HTML parsers (lxml,
    same as a real browser) recover from this by design, they don't
    reject it."""
    text = extract_html_content(malformed_path)
    assert "Unclosed paragraph" in text
    assert "another paragraph" in text


def test_extract_html_content_returns_empty_string_for_a_real_empty_body(empty_body_path):
    """Vision critique Q4, part 2: a genuinely empty page (a real,
    valid <body></body> with nothing in it) does NOT raise either --
    same "valid, trivial content" treatment an empty TXT/Markdown file
    already gets elsewhere in this pipeline."""
    assert extract_html_content(empty_body_path) == ""


def test_extract_html_content_raises_for_a_comment_only_document(comment_only_path):
    """Real, reproducible failure case (see this module's own
    docstring): a file containing only an HTML comment passes upload
    validation (a genuine, spec-defined HTML byte pattern) but has ZERO
    parseable elements under lxml -- readability-lxml's own real
    Unparseable (a ValueError subclass) surfaces here rather than being
    silently swallowed."""
    with pytest.raises(ValueError):
        extract_html_content(comment_only_path)


def test_extract_html_content_raises_for_real_binary_content(binary_path):
    """Inherited from api/services/txt_extraction.py -- reused here the
    same way Markdown reuses it."""
    with pytest.raises(ValueError):
        extract_html_content(binary_path)


# -------------------------------------------------------------- metadata --

def test_extract_html_metadata_prefers_open_graph_over_plain_tags(article_path):
    """Validation criterion: title/author/date/description metadata is
    extracted. Deliberate editorial choice: og:title/og:description win
    over the plainer <title> tag / meta description when both exist."""
    metadata = extract_html_metadata(article_path)
    assert metadata["title"] == "OG Title Wins"
    assert metadata["author"] == "Jane Doe"
    assert metadata["date"] == "2026-01-15T10:00:00Z"
    assert metadata["description"] == "A short description of the article."


def test_extract_html_metadata_returns_the_real_keywords_meta_tag(article_path):
    """Partie 2.2.5 -- the real, standard `<meta name="keywords">` tag."""
    metadata = extract_html_metadata(article_path)
    assert metadata["keywords"] == "alpha, beta, gamma"


def test_extract_html_metadata_falls_back_to_the_title_tag_when_no_og_title(no_og_meta_path):
    metadata = extract_html_metadata(no_og_meta_path)
    assert metadata["title"] == "Only A Title Tag"
    assert "author" not in metadata
    assert "date" not in metadata
    assert "description" not in metadata


def test_extract_html_metadata_falls_back_to_a_real_time_tag_for_the_date(time_tag_path):
    metadata = extract_html_metadata(time_tag_path)
    assert metadata["date"] == "2026-02-20T09:00:00Z"


def test_extract_html_metadata_returns_an_empty_dict_for_a_page_with_no_metadata_at_all(comment_only_path):
    """A comment-only page has no <head>/meta tags either -- this must
    not raise (unlike extract_html_content on the same file, which
    goes through readability, not plain BeautifulSoup tag lookups)."""
    assert extract_html_metadata(comment_only_path) == {}


# ----------------------------------------------------------------- links --

def test_extract_html_links_finds_every_distinct_real_link(article_path):
    """Validation criterion (optional item): link extraction works,
    including nav/footer links readability's own article extraction
    deliberately excludes from the main content."""
    links = extract_html_links(article_path)
    assert {link["href"] for link in links} == {"/", "/about", "/privacy"}
    home = next(link for link in links if link["href"] == "/")
    assert home["text"] == "Home"


def test_extract_html_links_returns_an_empty_list_when_there_are_none(empty_body_path):
    assert extract_html_links(empty_body_path) == []


# ----------------------------------------------------------------- tables (Partie 3.1.4) --

def test_extract_tables_html_finds_a_real_table(tmp_path):
    """Validation criterion: l'extraction de tableaux HTML fonctionne."""
    path = tmp_path / "table.html"
    path.write_bytes(b"<html><body><table><tr><th>Name</th><th>Value</th></tr><tr><td>a</td><td>1</td></tr></table></body></html>")

    tables = extract_tables_html(str(path))
    assert len(tables) == 1
    assert list(tables[0].columns) == ["Name", "Value"]
    assert tables[0].iloc[0].tolist() == ["a", 1]


def test_extract_tables_html_finds_every_real_table_in_document_order(tmp_path):
    path = tmp_path / "tables.html"
    path.write_bytes(
        b"<html><body>"
        b"<table><tr><th>A</th></tr><tr><td>1</td></tr></table>"
        b"<table><tr><th>B</th></tr><tr><td>2</td></tr></table>"
        b"</body></html>"
    )
    tables = extract_tables_html(str(path))
    assert len(tables) == 2
    assert list(tables[0].columns) == ["A"]
    assert list(tables[1].columns) == ["B"]


def test_extract_tables_html_returns_an_empty_list_for_a_page_with_no_table(article_path):
    assert extract_tables_html(article_path) == []

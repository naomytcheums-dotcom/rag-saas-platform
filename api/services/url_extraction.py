"""
Partie 2.1.10 -- extracting real main content and metadata from an
already-fetched web page. Deliberately reuses
`api/services/html_extraction.py`'s real, already-verified string-based
cores (`extract_html_content_from_markup`/`extract_html_metadata_from_markup`
-- readability-lxml's real article extraction, BeautifulSoup4's real
`<head>` metadata parsing) rather than a second, parallel HTML-parsing
implementation: a fetched web page IS the exact same real HTML Partie
2.1.5 already knows how to read, just sourced from a live URL instead
of an uploaded file. See that module's own docstring for why the shared
cores exist.

**`extract_url_metadata` adds one real field neither the shared core
nor an uploaded HTML file could ever have: `source_url`** -- an
uploaded file has no notion of "the URL it came from"; a fetched page
always does, and it is real, useful provenance (the eventual
`Document.source_url` column, and a sensible real title fallback when
a page has none -- see this function's own docstring).
"""

from api.services.html_extraction import extract_html_content_from_markup, extract_html_metadata_from_markup


def extract_url_main_content(url: str, html: str) -> str:
    """Item 2's literal function -- the real main-content text (article
    body, boilerplate stripped), identical logic to
    `extract_html_content_from_markup` (an uploaded HTML file and a
    fetched page are extracted exactly the same way once you have the
    real markup) -- `url` is accepted, per the literal signature this
    step's own spec asks for, but not needed by the extraction itself;
    `extract_url_metadata` below is where the URL is actually real,
    load-bearing information."""
    return extract_html_content_from_markup(html)


def extract_url_metadata(url: str, html: str) -> dict:
    """Item 2's literal function -- the same real title/author/date/
    description `extract_html_metadata_from_markup` already extracts,
    plus `source_url` (real, and something no uploaded file has). A
    real, honest fallback for `title` when the page declares none at
    all: the URL itself -- a document imported from a URL has no
    filename the way an upload does, so this is the one real,
    sensible source for a human-readable `Document.name` at import
    time (see api/security/documents.py's own import_document_from_url)."""
    metadata = extract_html_metadata_from_markup(html)
    metadata["source_url"] = url
    if "title" not in metadata:
        metadata["title"] = url
    return metadata

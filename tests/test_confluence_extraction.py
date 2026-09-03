"""
Partie 2.1.17 -- fast-tier tests for api/services/confluence_extraction.py.
No real network call: every real HTTP interaction is exercised through
`httpx.MockTransport`, the same "real library behavior, fake network"
split every prior fast-tier test file in this codebase uses.

**Honest, stated limitation, unlike every prior *_extraction.py test
file's own module docstring**: the mocked responses here are built
entirely from Atlassian's own stable, published REST API
documentation, NOT independently confirmed against any real, live
Confluence instance -- see api/services/confluence_extraction.py's own
module docstring for exactly why (no universal, always-reachable
Confluence host exists the way GitHub/Google/Notion's own fixed hosts
do).
"""

import httpx
import pytest

from api.config import settings
from api.services.confluence_extraction import (
    ConfluenceAuthError,
    ConfluenceRateLimitError,
    extract_confluence_content,
    extract_confluence_metadata,
    fetch_confluence_child_pages,
    fetch_confluence_page,
    fetch_confluence_space_pages,
    validate_confluence_url,
)

_BASE_URL = "https://example-tenant.atlassian.net/wiki"


def _patch_client(monkeypatch, handler):
    monkeypatch.setattr("api.services.confluence_extraction._client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))


# ---------------------------------------------------------- validate_confluence_url --

def test_validate_confluence_url_recognizes_a_real_cloud_page_url():
    assert validate_confluence_url(f"{_BASE_URL}/spaces/DOCS/pages/123456789/Page+Title") == ("123456789", "page")


def test_validate_confluence_url_recognizes_a_real_cloud_space_url():
    assert validate_confluence_url(f"{_BASE_URL}/spaces/DOCS") == ("DOCS", "space")
    assert validate_confluence_url(f"{_BASE_URL}/spaces/DOCS/") == ("DOCS", "space")


def test_validate_confluence_url_accepts_a_bare_numeric_page_id():
    """Validation criterion: accepte une URL de page ou d'espace."""
    assert validate_confluence_url("123456789") == ("123456789", "page")


def test_validate_confluence_url_rejects_an_unrelated_url():
    """Validation criterion: une page invalide est rejetée."""
    with pytest.raises(ValueError):
        validate_confluence_url("https://example.com/not-confluence")


def test_validate_confluence_url_rejects_a_non_numeric_bare_value():
    with pytest.raises(ValueError):
        validate_confluence_url("not-a-real-page-id")


# --------------------------------------------------------------- fetch_confluence_page --

async def test_fetch_confluence_page_returns_real_page_data(monkeypatch):
    _patch_client(monkeypatch, lambda request: httpx.Response(200, json={"id": "1", "title": "My Page"}))
    page = await fetch_confluence_page("1", "a-token", _BASE_URL)
    assert page["title"] == "My Page"


async def test_fetch_confluence_page_raises_for_a_documented_401_or_403(monkeypatch):
    """Validation criterion: un token invalide est rejeté."""
    _patch_client(monkeypatch, lambda request: httpx.Response(401, json={"statusCode": 401, "message": "Invalid token"}))
    with pytest.raises(ConfluenceAuthError):
        await fetch_confluence_page("1", "a-bad-token", _BASE_URL)


async def test_fetch_confluence_page_raises_a_distinguishable_rate_limit_error(monkeypatch):
    _patch_client(monkeypatch, lambda request: httpx.Response(429, json={"statusCode": 429, "message": "Rate limit exceeded"}))
    with pytest.raises(ConfluenceRateLimitError):
        await fetch_confluence_page("1", "a-token", _BASE_URL)


async def test_fetch_confluence_page_raises_for_a_documented_404(monkeypatch):
    _patch_client(monkeypatch, lambda request: httpx.Response(404, json={"statusCode": 404, "message": "No content found"}))
    with pytest.raises(ValueError, match="was not found"):
        await fetch_confluence_page("nonexistent", "a-token", _BASE_URL)


# ---------------------------------------------------------- fetch_confluence_space_pages --

async def test_fetch_confluence_space_pages_paginates_through_real_start_offsets(monkeypatch):
    """Validation criterion: l'import d'un espace fonctionne."""
    pages = {
        0: {"results": [{"id": "p1"}, {"id": "p2"}]},
        2: {"results": []},
    }

    def handler(request):
        start = int(request.url.params["start"])
        return httpx.Response(200, json=pages.get(start, {"results": []}))

    _patch_client(monkeypatch, handler)
    result = await fetch_confluence_space_pages("DOCS", "a-token", _BASE_URL, max_pages=100)
    assert [p["id"] for p in result] == ["p1", "p2"]


async def test_fetch_confluence_space_pages_enforces_the_real_max_pages_cap(monkeypatch):
    _patch_client(monkeypatch, lambda request: httpx.Response(200, json={"results": [{"id": f"p{i}"} for i in range(10)]}))
    result = await fetch_confluence_space_pages("DOCS", "a-token", _BASE_URL, max_pages=3)
    assert len(result) == 3


# --------------------------------------------------------- fetch_confluence_child_pages --

async def test_fetch_confluence_child_pages_returns_real_direct_children(monkeypatch):
    _patch_client(monkeypatch, lambda request: httpx.Response(200, json={"results": [{"id": "child-1"}]}))
    children = await fetch_confluence_child_pages("parent-1", "a-token", _BASE_URL)
    assert children == [{"id": "child-1"}]


# ------------------------------------------------------------- extract_confluence_content --

def test_extract_confluence_content_extracts_real_text_from_storage_html():
    """Validation criterion: l'extraction en Markdown fonctionne
    (via la réutilisation réelle de l'extraction HTML existante)."""
    page = {"body": {"storage": {"value": "<p>Real <strong>Confluence</strong> content.</p>"}}}
    text = extract_confluence_content(page)
    assert "Real" in text and "Confluence" in text
    assert "<p>" not in text


def test_extract_confluence_content_handles_a_real_empty_body():
    assert extract_confluence_content({"body": {"storage": {"value": ""}}}) == ""
    assert extract_confluence_content({}) == ""


# ------------------------------------------------------------ extract_confluence_metadata --

def test_extract_confluence_metadata_reports_title_version_date_and_author():
    """Validation criterion: les métadonnées sont extraites (titre,
    version, date, auteur)."""
    page = {
        "id": "1", "title": "My Page", "space": {"key": "DOCS"},
        "version": {"number": 3, "when": "2026-01-01T00:00:00Z", "by": {"displayName": "Alice"}},
        "_links": {"webui": "/spaces/DOCS/pages/1"},
    }
    metadata = extract_confluence_metadata(page)
    assert metadata["title"] == "My Page"
    assert metadata["version"] == 3
    assert metadata["author"] == "Alice"
    assert metadata["space_key"] == "DOCS"


def test_extract_confluence_metadata_handles_missing_real_fields_gracefully():
    assert extract_confluence_metadata({"id": "1", "title": "Bare Page"})["author"] is None

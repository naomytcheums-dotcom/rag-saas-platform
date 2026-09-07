"""Partie 5.2.2 -- web search tool (Tavily). Real httpx.MockTransport
-- real request/response parsing, fake network transport, same
precedent as tests/test_github_extraction.py."""

import httpx
import pytest

from api.config import settings
from api.tools.web_search import (
    WEB_SEARCH_TOOL, WebSearchError, extract_web_search_results, format_web_search_results, web_search,
    web_search_with_context,
)


def _patch_client(monkeypatch, handler):
    monkeypatch.setattr("api.tools.web_search._client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))


@pytest.fixture(autouse=True)
def _configure_key(monkeypatch):
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "tvly-test-key")


_REAL_SHAPED_RESPONSE = {
    "query": "latest AI news",
    "answer": "AI news summary.",
    "results": [{"title": "Big AI Announcement", "url": "https://example.com/ai", "content": "Something happened.", "score": 0.9}],
}


# --------------------------------------- web_search --


async def test_web_search_returns_real_results(monkeypatch):
    """Validation criterion: la recherche web fonctionne (mock)."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://api.tavily.com/search"
        body = request.read()
        import json
        payload = json.loads(body)
        assert payload["query"] == "latest AI news"
        assert payload["api_key"] == "tvly-test-key"
        return httpx.Response(200, json=_REAL_SHAPED_RESPONSE)

    _patch_client(monkeypatch, handler)
    result = await web_search("latest AI news")
    assert result["results"][0]["title"] == "Big AI Announcement"


async def test_web_search_respects_real_parameters(monkeypatch):
    """Validation criterion: les paramètres sont respectés."""
    import json

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.read())
        assert payload["search_depth"] == "advanced"
        assert payload["max_results"] == 3
        return httpx.Response(200, json=_REAL_SHAPED_RESPONSE)

    _patch_client(monkeypatch, handler)
    await web_search("query", search_depth="advanced", max_results=3)


async def test_web_search_passes_real_allowed_domains_as_include_domains(monkeypatch):
    """Validation criterion: Partie 5.3.9 -- un allowed_domains par
    agent est bien transmis à Tavily."""
    import json

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.read())
        assert payload["include_domains"] == ["acme.com"]
        return httpx.Response(200, json=_REAL_SHAPED_RESPONSE)

    _patch_client(monkeypatch, handler)
    await web_search("query", allowed_domains=["acme.com"])


async def test_web_search_with_context_forces_real_raw_content(monkeypatch):
    import json

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.read())
        assert payload["include_raw_content"] is True
        assert payload["search_depth"] == "advanced"
        return httpx.Response(200, json=_REAL_SHAPED_RESPONSE)

    _patch_client(monkeypatch, handler)
    await web_search_with_context("query")


async def test_web_search_raises_without_a_real_api_key(monkeypatch):
    """Validation criterion: sécurité -- la clé API est requise."""
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "")
    with pytest.raises(WebSearchError, match="TAVILY_API_KEY"):
        await web_search("query")


async def test_web_search_maps_a_real_http_error(monkeypatch):
    """Validation criterion: robustesse -- les erreurs sont gérées."""
    _patch_client(monkeypatch, lambda request: httpx.Response(401, json={"detail": "invalid key"}))
    with pytest.raises(WebSearchError, match="401"):
        await web_search("query")


async def test_web_search_maps_a_real_timeout(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    _patch_client(monkeypatch, handler)
    with pytest.raises(WebSearchError, match="timed out"):
        await web_search("query")


# --------------------------------------- extract / format --


def test_extract_web_search_results():
    assert extract_web_search_results(_REAL_SHAPED_RESPONSE) == _REAL_SHAPED_RESPONSE["results"]


def test_format_web_search_results_includes_the_real_answer_and_sources():
    formatted = format_web_search_results(_REAL_SHAPED_RESPONSE)
    assert "AI news summary." in formatted
    assert "Big AI Announcement" in formatted


def test_format_web_search_results_handles_no_results():
    assert format_web_search_results({"results": []}) == "No web results found."


# --------------------------------------- tool wiring --


async def test_web_search_tool_handler_works(monkeypatch):
    _patch_client(monkeypatch, lambda request: httpx.Response(200, json=_REAL_SHAPED_RESPONSE))
    result = await WEB_SEARCH_TOOL.handler(query="latest AI news")
    assert "Big AI Announcement" in result

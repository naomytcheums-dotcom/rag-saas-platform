"""Partie 5.4.5 -- Search workflow block. Real httpx.MockTransport at
the Tavily boundary, same precedent as tests/test_web_search.py."""

import json

import httpx
import pytest

from api.config import settings
from api.services.workflow_block_search import (
    execute_search_block, format_search_results, render_search_query, validate_search_config,
)
from api.services.workflow_blocks import WorkflowBlockError


def _patch_client(monkeypatch, handler):
    monkeypatch.setattr("api.tools.web_search._client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))


@pytest.fixture(autouse=True)
def _configure_key(monkeypatch):
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "tvly-test-key")


_REAL_SHAPED_RESPONSE = {
    "query": "latest AI news", "answer": "AI news summary.",
    "results": [{"title": "Big AI Announcement", "url": "https://example.com/ai", "content": "Something happened.", "score": 0.9}],
}


# --------------------------------------- validate_search_config / render_search_query / format_search_results --


def test_validate_search_config_accepts_a_real_valid_config():
    validate_search_config({"query": "{{topic}}", "search_depth": "advanced", "max_results": 5})


def test_validate_search_config_rejects_a_missing_query():
    """Validation criterion: la validation fonctionne."""
    with pytest.raises(WorkflowBlockError, match="query"):
        validate_search_config({})


def test_validate_search_config_rejects_an_unknown_search_depth():
    with pytest.raises(WorkflowBlockError, match="search_depth"):
        validate_search_config({"query": "q", "search_depth": "deep"})


def test_validate_search_config_rejects_a_non_positive_max_results():
    with pytest.raises(WorkflowBlockError):
        validate_search_config({"query": "q", "max_results": 0})


def test_render_search_query_substitutes_real_variables():
    """Validation criterion: le rendu des requêtes fonctionne."""
    assert render_search_query("News about {{topic}}", {"topic": "AI"}) == "News about AI"


def test_format_search_results_reuses_the_real_web_search_formatter():
    """Validation criterion: les résultats sont formatés."""
    formatted = format_search_results(_REAL_SHAPED_RESPONSE)
    assert "Big AI Announcement" in formatted


# --------------------------------------- execute_search_block --


async def test_execute_search_block_returns_formatted_results(monkeypatch):
    """Validation criterion: l'exécution du bloc Search fonctionne."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_REAL_SHAPED_RESPONSE)

    _patch_client(monkeypatch, handler)
    result = await execute_search_block({"query": "AI news", "output_key": "news"}, {})
    assert "Big AI Announcement" in result["news"]


async def test_execute_search_block_renders_real_query_variables(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.read())
        assert payload["query"] == "News about invoices"
        return httpx.Response(200, json=_REAL_SHAPED_RESPONSE)

    _patch_client(monkeypatch, handler)
    await execute_search_block({"query": "News about {{topic}}"}, {"topic": "invoices"})


async def test_execute_search_block_passes_real_include_and_exclude_domains(monkeypatch):
    """Validation criterion: cohérence -- réutilise le vrai outil web_search (5.2.2)."""
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.read())
        assert payload["include_domains"] == ["acme.com"]
        assert payload["exclude_domains"] == ["spam.com"]
        return httpx.Response(200, json=_REAL_SHAPED_RESPONSE)

    _patch_client(monkeypatch, handler)
    await execute_search_block({"query": "q", "include_domains": ["acme.com"], "exclude_domains": ["spam.com"]}, {})


async def test_execute_search_block_wraps_a_real_search_failure(monkeypatch):
    """Validation criterion: robustesse -- que se passe-t-il si la recherche échoue."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    _patch_client(monkeypatch, handler)
    with pytest.raises(WorkflowBlockError, match="web_search block failed"):
        await execute_search_block({"query": "q"}, {})


async def test_execute_search_block_raises_on_invalid_config():
    with pytest.raises(WorkflowBlockError):
        await execute_search_block({}, {})

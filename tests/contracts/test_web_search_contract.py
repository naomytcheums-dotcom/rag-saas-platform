"""Spec 5.2.2 web search (Tavily) -- CONTRACT tests against a LOCAL FAKE Tavily server (real product code + real httpx, fake vendor).
Real validation: scripts/validate_tavily_live.py."""

import pytest

from api.config import settings
from api.tools import web_search as module
from api.tools.web_search import WebSearchError, format_web_search_results, web_search, web_search_with_context
from vendor_fakes import FakeVendor, Resp, closed_url

TAVILY_OK = {
    "query": "rag", "answer": "RAG is retrieval augmented generation.", "response_time": 0.8,
    "results": [{"title": "RAG explained", "url": "https://example.com/rag", "content": "RAG combines retrieval and generation.", "score": 0.93, "raw_content": None}],
}


@pytest.fixture(autouse=True)
def _config(monkeypatch):
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "tvly-contract-key")
    monkeypatch.setattr(settings, "TAVILY_INCLUDE_DOMAINS", [])
    monkeypatch.setattr(settings, "TAVILY_EXCLUDE_DOMAINS", [])

    async def instant(_):
        return None

    monkeypatch.setattr(module.asyncio, "sleep", instant)


@pytest.fixture
def tavily(monkeypatch):
    with FakeVendor() as fake:
        monkeypatch.setattr(module, "_TAVILY_URL", f"{fake.url}/search")
        yield fake


async def test_request_shape_and_parsed_results(tavily):
    tavily.on("POST", "/search", Resp(200, TAVILY_OK))
    result = await web_search("rag", search_depth="basic", max_results=3, allowed_domains=["example.com"], exclude_domains=["spam.test"])
    (request,) = tavily.requests
    assert request.headers["authorization"] == "Bearer tvly-contract-key"
    body = request.json()
    assert body["query"] == "rag" and body["search_depth"] == "basic" and body["max_results"] == 3
    assert body["include_domains"] == ["example.com"] and body["exclude_domains"] == ["spam.test"]  # enforced server-side
    assert result["results"][0]["url"] == "https://example.com/rag"
    text = format_web_search_results(result)
    assert text.startswith("Summary: RAG is retrieval augmented generation.") and "[RAG explained](https://example.com/rag)" in text


async def test_with_context_forces_raw_content_and_advanced_depth(tavily):
    tavily.on("POST", "/search", Resp(200, TAVILY_OK))
    await web_search_with_context("rag")
    body = tavily.requests[0].json()
    assert body["include_raw_content"] is True and body["search_depth"] == "advanced"


async def test_missing_key_fails_before_any_request(tavily, monkeypatch):
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "")
    with pytest.raises(WebSearchError, match="TAVILY_API_KEY"):
        await web_search("rag")
    assert tavily.requests == []


@pytest.mark.parametrize("status,detail", [(401, "Unauthorized: missing or invalid API key."), (432, "Plan usage limit exceeded."), (400, "Query is too long.")])
async def test_client_errors_are_typed_and_not_retried(tavily, status, detail):
    tavily.on("POST", "/search", Resp(status, {"detail": {"error": detail}}))
    with pytest.raises(WebSearchError, match=str(status)):
        await web_search("rag")
    assert len(tavily.requests) == 1


async def test_rate_limit_is_retried_with_retry_after_then_succeeds(tavily):
    tavily.on("POST", "/search", [Resp(429, {"detail": {"error": "Too many requests"}}, headers={"retry-after": "1"}), Resp(200, TAVILY_OK)])
    assert (await web_search("rag"))["answer"].startswith("RAG")
    assert len(tavily.requests) == 2


async def test_persistent_outage_gives_up_after_three_attempts(tavily):
    tavily.on("POST", "/search", Resp(503, {"detail": {"error": "unavailable"}}))
    with pytest.raises(WebSearchError, match="503"):
        await web_search("rag")
    assert len(tavily.requests) == 3


async def test_timeout_and_unreachable_vendor(tavily, monkeypatch):
    monkeypatch.setattr(module, "_TIMEOUT_SECONDS", 0.3)
    tavily.on("POST", "/search", Resp(200, TAVILY_OK, delay=1.5))
    with pytest.raises(WebSearchError, match="timed out"):
        await web_search("rag")
    monkeypatch.setattr(module, "_TIMEOUT_SECONDS", 5.0)
    monkeypatch.setattr(module, "_TAVILY_URL", f"{closed_url()}/search")
    with pytest.raises(WebSearchError, match="Could not reach"):
        await web_search("rag")


async def test_a_non_json_answer_is_a_typed_error(tavily):
    tavily.on("POST", "/search", Resp(200, "<html>gateway</html>"))
    with pytest.raises(WebSearchError, match="not JSON"):
        await web_search("rag")


async def test_empty_result_list_is_rendered_honestly(tavily):
    tavily.on("POST", "/search", Resp(200, {"query": "zzz", "results": []}))
    assert format_web_search_results(await web_search("zzz")) == "No web results found."

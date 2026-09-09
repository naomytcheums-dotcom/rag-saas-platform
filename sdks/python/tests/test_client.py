"""Real tests using httpx's own real `MockTransport` -- exercises the
real request-building/response-parsing logic end to end, without a
real network call or a real running backend."""

import json

import httpx
import pytest

from rag_saas_sdk import RagSaasClient
from rag_saas_sdk.errors import RagSaasAPIError


def _client_with_transport(handler) -> RagSaasClient:
    client = RagSaasClient(api_key="pk_test", base_url="https://test.example.com")
    client._http = httpx.Client(base_url="https://test.example.com", headers={"X-API-Key": "pk_test"}, transport=httpx.MockTransport(handler))
    return client


def test_chat_send():
    """Validation criterion: le SDK généré est fonctionnel (chat)."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat"
        assert request.headers["X-API-Key"] == "pk_test"
        body = json.loads(request.content)
        assert body["message"] == "Hi"
        return httpx.Response(200, json={"message_id": "m1", "conversation_id": "c1", "response": "Hello!", "citations": [], "metadata": {}})

    client = _client_with_transport(handler)
    result = client.chat.send("Hi", agent_id="agent-1")
    assert result.response == "Hello!"
    assert result.conversation_id == "c1"


def test_search_query():
    """Validation criterion: les méthodes fonctionnent (search)."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": [{"text": "chunk"}], "total": 1, "query": "test", "metadata": {}})

    client = _client_with_transport(handler)
    result = client.search.query("test")
    assert result.total == 1


def test_agents_run():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"run_id": "r1", "output": "done", "conversation_id": None, "metadata": {}})

    client = _client_with_transport(handler)
    result = client.agents.run("agent-1", "do something")
    assert result.output == "done"


def test_usage_get():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"period": "month", "metrics": [], "breakdown": [], "total": 0})

    client = _client_with_transport(handler)
    result = client.usage.get()
    assert result.period == "month"


def test_analytics_get():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"period": "week", "metrics": [], "data": [], "summary": "ok"})

    client = _client_with_transport(handler)
    result = client.analytics.get(period="week")
    assert result.period == "week"


def test_embed_generate():
    """Validation criterion: complétude -- tous les endpoints couverts."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embedding": [0.1, 0.2], "model": "default", "dimensions": 2})

    client = _client_with_transport(handler)
    result = client.embed.generate("hello")
    assert result.dimensions == 2


def test_raises_rag_saas_api_error_on_failure():
    """Validation criterion: les erreurs sont gérées."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "Invalid API key"})

    client = _client_with_transport(handler)
    with pytest.raises(RagSaasAPIError) as exc_info:
        client.chat.send("Hi", agent_id="agent-1")
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid API key"


def test_raises_on_non_json_error_body():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal server error")

    client = _client_with_transport(handler)
    with pytest.raises(RagSaasAPIError) as exc_info:
        client.embed.generate("hello")
    assert exc_info.value.status_code == 500

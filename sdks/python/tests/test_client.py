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


# ---------------------------------- Hardening Mission, §21/§31: streaming + full /v1 coverage


def test_chat_stream_yields_real_server_sent_events():
    sse = (
        b'event: start\ndata: {}\n\n'
        b'event: token\ndata: {"token": "Hel"}\n\n'
        b'event: token\ndata: {"token": "lo"}\n\n'
        b'event: done\ndata: {}\n\n'
    )

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.url.path == "/v1/chat" and body["stream"] is True
        return httpx.Response(200, content=sse, headers={"Content-Type": "text/event-stream"})

    client = _client_with_transport(handler)
    events = list(client.chat.stream("Hi", agent_id="agent-1"))

    assert [e.event for e in events] == ["start", "token", "token", "done"]
    assert "".join(e.data.get("token", "") for e in events) == "Hello"


def test_chat_stream_raises_a_real_api_error_before_yielding_anything_on_http_failure():
    client = _client_with_transport(lambda request: httpx.Response(429, json={"detail": "Too many attempts"}))

    with pytest.raises(RagSaasAPIError) as exc_info:
        list(client.chat.stream("Hi", agent_id="agent-1"))

    assert exc_info.value.status_code == 429


def test_chat_send_refuses_stream_true_instead_of_crashing_on_an_event_stream_body():
    client = _client_with_transport(lambda request: httpx.Response(500))
    with pytest.raises(ValueError, match="chat.stream"):
        client.chat.send("Hi", agent_id="agent-1", stream=True)


def test_chat_send_always_asks_the_server_for_one_complete_response():
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["stream"] is False
        return httpx.Response(200, json={"message_id": "m1", "conversation_id": "c1", "response": "ok", "citations": [], "metadata": {}})

    assert _client_with_transport(handler).chat.send("Hi", agent_id="a").response == "ok"


def test_list_endpoints_cover_every_public_v1_route():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path, dict(request.url.params)))
        if request.url.path == "/v1/conversations":
            return httpx.Response(200, json={"items": [], "total": 0, "limit": 5, "offset": 0})
        if request.method == "POST":
            return httpx.Response(200, json={"id": "kb1", "name": "KB", "description": None, "created_at": "2026-01-01T00:00:00Z"})
        return httpx.Response(200, json=[])

    client = _client_with_transport(handler)
    assert client.agents.list(limit=5) == []
    assert client.documents.list(offset=10) == []
    assert client.knowledge_bases.list() == []
    assert client.conversations.list(limit=5, agent_id="agent-1").total == 0
    assert client.knowledge_bases.create("KB").id == "kb1"

    assert [(m, p) for m, p, _ in seen] == [
        ("GET", "/v1/agents"), ("GET", "/v1/documents"), ("GET", "/v1/knowledge-bases"),
        ("GET", "/v1/conversations"), ("POST", "/v1/knowledge-bases"),
    ]
    assert seen[0][2] == {"limit": "5", "offset": "0"} and seen[1][2]["offset"] == "10" and seen[3][2]["agent_id"] == "agent-1"

"""RAG-004: an agent configured to answer only from sources must refuse BEFORE generating when retrieval found nothing.

`/chat/stream` (the path the main UI uses) streams tokens as they are produced, so the post-hoc refusal gates of `run_agent` cannot
apply there: the client has already seen the tokens. Without context the model simply answered freely. The decision is now taken
before the model is called; agents that did not opt in (citation_required / answer_only_from_context are False by default) keep
streaming exactly as before. No model is called in these tests."""

from unittest.mock import AsyncMock, patch

import pytest

from api.models.agent import Agent
from test_document_idor import make_tenants

CHUNK = {"id": "c1", "document_id": "d1", "content": "Support is open Monday to Friday.", "score": 0.9}


async def _agent(client, db_session, monkeypatch, **flags):
    (headers, org_id, _user), _other = await make_tenants(client, db_session, monkeypatch, "refuse")
    agent = Agent(organization_id=org_id, name="A", system_prompt="You answer questions.", **flags)
    db_session.add(agent)
    await db_session.commit()
    return headers, agent.id


async def _stream(client, headers, agent_id, chunks):
    called = AsyncMock()

    async def fake_stream(*args, **kwargs):
        await called()
        yield "event: token\ndata: {\"token\": \"model answer\"}\n\n"
        yield "event: done\ndata: {}\n\n"

    with patch("api.routers.chat_stream.search_with_context", AsyncMock(return_value=chunks)), \
            patch("api.routers.chat_stream.stream_agent_response", fake_stream):
        response = await client.post("/chat/stream", json={"agent_id": str(agent_id), "message": "When is support open?"}, headers=headers)
    return response, called


async def test_a_citation_required_agent_refuses_without_context_and_never_calls_the_model(client, db_session, monkeypatch):
    headers, agent_id = await _agent(client, db_session, monkeypatch, citation_required=True, citation_required_message="No verified source.")
    response, called = await _stream(client, headers, agent_id, [])
    assert response.status_code == 200
    assert "No verified source." in response.text and '"gated": true' in response.text and "model answer" not in response.text
    called.assert_not_awaited()


async def test_a_context_only_agent_refuses_without_context(client, db_session, monkeypatch):
    headers, agent_id = await _agent(client, db_session, monkeypatch, answer_only_from_context=True)
    response, called = await _stream(client, headers, agent_id, [])
    assert '"reason": "no_context"' in response.text and "model answer" not in response.text
    called.assert_not_awaited()


async def test_the_default_refusal_text_is_used_when_none_is_configured(client, db_session, monkeypatch):
    from api.services.agent_citation_required import DEFAULT_CITATION_REQUIRED_MESSAGE

    headers, agent_id = await _agent(client, db_session, monkeypatch, citation_required=True)
    response, _called = await _stream(client, headers, agent_id, [])
    assert DEFAULT_CITATION_REQUIRED_MESSAGE in response.text


@pytest.mark.parametrize("flags", [{"citation_required": True}, {"answer_only_from_context": True}, {}])
async def test_with_context_the_model_is_called_as_before(client, db_session, monkeypatch, flags):
    headers, agent_id = await _agent(client, db_session, monkeypatch, **flags)
    response, called = await _stream(client, headers, agent_id, [CHUNK])
    assert "model answer" in response.text and '"gated"' not in response.text
    called.assert_awaited_once()


async def test_an_agent_that_did_not_opt_in_keeps_answering_without_context(client, db_session, monkeypatch):
    headers, agent_id = await _agent(client, db_session, monkeypatch)
    response, called = await _stream(client, headers, agent_id, [])
    assert "model answer" in response.text
    called.assert_awaited_once()

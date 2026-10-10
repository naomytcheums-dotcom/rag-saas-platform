"""Spec 1.3.7 -- per-user request limit on the authenticated chat stream. No model is called in these tests."""

from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from api.config import settings
from api.models.agent import Agent
from test_document_idor import make_tenants

CHUNK = {"id": "c1", "document_id": "d1", "content": "Support is open Monday to Friday.", "score": 0.9}


async def _agent(client, db_session, monkeypatch):
    (headers, org_id, user), _other = await make_tenants(client, db_session, monkeypatch, "chatlimit")
    agent = Agent(organization_id=org_id, name="A", system_prompt="You answer questions.")
    db_session.add(agent)
    await db_session.commit()
    return headers, agent.id, user


async def _post(client, headers, agent_id):
    async def fake_stream(*args, **kwargs):
        yield "event: token\ndata: {\"token\": \"hi\"}\n\n"
        yield "event: done\ndata: {}\n\n"

    with patch("api.routers.chat_stream.search_with_context", AsyncMock(return_value=[CHUNK])), patch("api.routers.chat_stream.stream_agent_response", fake_stream):
        return await client.post("/chat/stream", json={"agent_id": str(agent_id), "message": "hello?"}, headers=headers)


async def test_the_stream_is_rate_limited_per_user_with_the_configured_budget(client, db_session, monkeypatch):
    headers, agent_id, user = await _agent(client, db_session, monkeypatch)
    limiter = AsyncMock()
    with patch("api.security.rate_limit.enforce_rate_limit", limiter):
        response = await _post(client, headers, agent_id)
    assert response.status_code == 200
    key, max_attempts, window = limiter.await_args.args
    assert key == f"ratelimit:chat_stream:user:{user}"
    assert (max_attempts, window) == (settings.CHAT_USER_RATE_LIMIT_MAX_ATTEMPTS, settings.CHAT_USER_RATE_LIMIT_WINDOW_SECONDS)


async def test_an_exhausted_budget_answers_429_before_any_work_is_done(client, db_session, monkeypatch):
    headers, agent_id, _user = await _agent(client, db_session, monkeypatch)
    limiter = AsyncMock(side_effect=HTTPException(status_code=429, detail="Too many requests", headers={"Retry-After": "30"}))
    search = AsyncMock(return_value=[CHUNK])
    with patch("api.security.rate_limit.enforce_rate_limit", limiter), patch("api.routers.chat_stream.search_with_context", search):
        response = await client.post("/chat/stream", json={"agent_id": str(agent_id), "message": "hello?"}, headers=headers)
    assert response.status_code == 429 and response.headers["retry-after"] == "30"
    search.assert_not_awaited()


async def test_the_budget_is_not_consulted_for_a_user_without_access_to_the_agent(client, db_session, monkeypatch):
    (_headers, org_id, _user), (other_headers, _o, _u) = await make_tenants(client, db_session, monkeypatch, "chatlimit2")
    agent = Agent(organization_id=org_id, name="A", system_prompt="x")
    db_session.add(agent)
    await db_session.commit()
    limiter = AsyncMock()
    with patch("api.security.rate_limit.enforce_rate_limit", limiter):
        response = await client.post("/chat/stream", json={"agent_id": str(agent.id), "message": "hi"}, headers=other_headers)
    assert response.status_code in (403, 404)
    limiter.assert_not_awaited()

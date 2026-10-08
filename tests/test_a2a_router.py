"""Hardening Mission, §15 (A2A) -- the real HTTP transport for
`api/services/a2a_integration.py`. Before this router existed the
executor was UNWIRED (nothing called it). The A2A SDK's real
`DefaultRequestHandler` + `JsonRpcDispatcher` run for real here; only
`run_requirement_agent` (a paid BeeAI/LLM call) is mocked at its own
already-tested boundary."""

import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from api.config import settings
from api.models.billing import Credit

_A2A_HEADERS = {"A2A-Version": "1.0"}


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _make_org_with_key(client, db_session, register_payload, scopes, org_name="A2A Org"):
    payload = {"email": register_payload["email"], "password": register_payload["password"], "accept_terms": True}
    from unittest.mock import patch

    with patch("api.routers.auth.create_and_send_email_otp", new=AsyncMock()):
        token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    org_id = (await client.post("/organizations", json={"name": org_name}, headers=_auth_header(token))).json()["id"]
    created = await client.post(f"/organizations/{org_id}/api-keys", json={"name": "a2a-key", "scopes": scopes}, headers=_auth_header(token))
    return org_id, created.json()["key"]


def _send_message(text: str) -> dict:
    return {
        "jsonrpc": "2.0", "id": "1", "method": "SendMessage",
        "params": {"message": {"messageId": uuid.uuid4().hex, "role": "ROLE_USER", "parts": [{"text": text}]}},
    }


async def _set_balance(db_session, org_id: str, balance: int) -> None:
    credit = await db_session.scalar(select(Credit).where(Credit.organization_id == uuid.UUID(org_id)))
    if credit is None:
        credit = Credit(organization_id=uuid.UUID(org_id), balance=balance)
        db_session.add(credit)
    else:
        credit.balance = balance
    await db_session.commit()


async def test_agent_card_requires_an_api_key(client):
    response = await client.get(f"/a2a/{uuid.uuid4()}/.well-known/agent-card.json")
    assert response.status_code in (401, 422)


async def test_agent_card_rejects_a_key_without_the_a2a_scope(client, db_session, register_payload):
    org_id, api_key = await _make_org_with_key(client, db_session, register_payload, ["chat:read"])
    response = await client.get(f"/a2a/{org_id}/.well-known/agent-card.json", headers={"X-API-Key": api_key})
    assert response.status_code == 403


async def test_agent_card_describes_the_callers_own_organization(client, db_session, register_payload):
    org_id, api_key = await _make_org_with_key(client, db_session, register_payload, ["a2a:call"], org_name="Acme Corp")
    response = await client.get(f"/a2a/{org_id}/.well-known/agent-card.json", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Acme Corp RAG Agent"
    assert body["skills"][0]["id"] == "rag_query"


async def test_a_key_can_never_address_another_organization(client, db_session, register_payload):
    """Multi-tenant isolation: a valid key for org A, aimed at org B's
    path, gets a plain 404 -- indistinguishable from a nonexistent org."""
    _org_id, api_key = await _make_org_with_key(client, db_session, register_payload, ["a2a:call"])
    other_org = uuid.uuid4()
    card = await client.get(f"/a2a/{other_org}/.well-known/agent-card.json", headers={"X-API-Key": api_key})
    rpc = await client.post(f"/a2a/{other_org}", json=_send_message("hi"), headers={"X-API-Key": api_key, **_A2A_HEADERS})
    assert card.status_code == 404
    assert rpc.status_code == 404


async def test_a2a_task_runs_the_real_agent_and_debits_credits(monkeypatch, client, db_session, register_payload):
    org_id, api_key = await _make_org_with_key(client, db_session, register_payload, ["a2a:call"])
    await _set_balance(db_session, org_id, 1000)
    mock_agent = AsyncMock(return_value="Paris is the capital of France.")
    monkeypatch.setattr("api.services.beeai_orchestrator.run_requirement_agent", mock_agent)

    response = await client.post(
        f"/a2a/{org_id}", json=_send_message("What is the capital of France?"), headers={"X-API-Key": api_key, **_A2A_HEADERS},
    )

    assert response.status_code == 200, response.text
    assert "Paris is the capital of France." in response.text
    mock_agent.assert_awaited_once()
    assert mock_agent.await_args.args[2] == "What is the capital of France?"
    db_session.expire_all()
    credit = await db_session.scalar(select(Credit).where(Credit.organization_id == uuid.UUID(org_id)))
    assert credit.balance == 1000 - settings.A2A_TASK_CREDIT_COST


async def test_a2a_task_is_refused_before_any_llm_call_with_a_zero_balance(monkeypatch, client, db_session, register_payload):
    org_id, api_key = await _make_org_with_key(client, db_session, register_payload, ["a2a:call"])
    await _set_balance(db_session, org_id, 0)
    mock_agent = AsyncMock(return_value="should never run")
    monkeypatch.setattr("api.services.beeai_orchestrator.run_requirement_agent", mock_agent)

    response = await client.post(f"/a2a/{org_id}", json=_send_message("hi"), headers={"X-API-Key": api_key, **_A2A_HEADERS})

    assert response.status_code == 402
    mock_agent.assert_not_awaited()


async def test_a2a_task_is_refused_when_balance_is_below_task_cost(monkeypatch, client, db_session, register_payload):
    org_id, api_key = await _make_org_with_key(client, db_session, register_payload, ["a2a:call"])
    await _set_balance(db_session, org_id, settings.A2A_TASK_CREDIT_COST - 1)
    mock_agent = AsyncMock(return_value="should never run")
    monkeypatch.setattr("api.services.beeai_orchestrator.run_requirement_agent", mock_agent)

    response = await client.post(f"/a2a/{org_id}", json=_send_message("hi"), headers={"X-API-Key": api_key, **_A2A_HEADERS})

    assert response.status_code == 402
    mock_agent.assert_not_awaited()


async def test_a2a_debits_platform_credits_before_calling_the_agent(monkeypatch, client, db_session, register_payload):
    org_id, api_key = await _make_org_with_key(client, db_session, register_payload, ["a2a:call"])
    initial_balance = settings.A2A_TASK_CREDIT_COST * 2
    await _set_balance(db_session, org_id, initial_balance)

    async def _agent_after_debit(db, organization_id, task):
        credit = await db.scalar(select(Credit).where(Credit.organization_id == organization_id))
        assert credit.balance == initial_balance - settings.A2A_TASK_CREDIT_COST
        return "answer"

    mock_agent = AsyncMock(side_effect=_agent_after_debit)
    monkeypatch.setattr("api.services.beeai_orchestrator.run_requirement_agent", mock_agent)

    response = await client.post(f"/a2a/{org_id}", json=_send_message("hi"), headers={"X-API-Key": api_key, **_A2A_HEADERS})

    assert response.status_code == 200, response.text
    mock_agent.assert_awaited_once()


async def test_a2a_rolls_back_reserved_credits_when_agent_execution_fails(monkeypatch, db_session, register_payload, client):
    from api.routers.a2a import _BilledRagAgentExecutor, _session_factory_for
    from api.services.a2a_integration import RagAgentExecutor

    org_id, _api_key = await _make_org_with_key(client, db_session, register_payload, ["a2a:call"])
    initial_balance = settings.A2A_TASK_CREDIT_COST * 2
    await _set_balance(db_session, org_id, initial_balance)

    async def _failed_execution(self, context, event_queue):
        raise RuntimeError("provider failed")

    monkeypatch.setattr(RagAgentExecutor, "execute", _failed_execution)
    executor = _BilledRagAgentExecutor(
        db_session_factory=_session_factory_for(db_session),
        organization_id=uuid.UUID(org_id),
    )

    with pytest.raises(RuntimeError, match="provider failed"):
        await executor.execute(None, None)

    db_session.expire_all()
    credit = await db_session.scalar(select(Credit).where(Credit.organization_id == uuid.UUID(org_id)))
    assert credit.balance == initial_balance


async def test_a2a_task_is_refused_once_the_daily_spend_cap_is_reached(monkeypatch, client, db_session, register_payload):
    import datetime as dt

    from api.models.billing import CreditTransaction, CreditTransactionType

    org_id, api_key = await _make_org_with_key(client, db_session, register_payload, ["a2a:call"])
    await _set_balance(db_session, org_id, 1000)
    db_session.add(CreditTransaction(
        organization_id=uuid.UUID(org_id), type=CreditTransactionType.consume, amount=-100, balance_after=900,
        reason="llm_call:test", created_at=dt.datetime.now(dt.timezone.utc),
    ))
    await db_session.commit()
    owner_token = (await client.post("/auth/login", json={"email": register_payload["email"], "password": register_payload["password"]})).json()["access_token"]
    patched = await client.patch(f"/organizations/{org_id}/settings", json={"daily_credit_limit": 100}, headers=_auth_header(owner_token))
    assert patched.status_code == 200, patched.text
    mock_agent = AsyncMock(return_value="should never run")
    monkeypatch.setattr("api.services.beeai_orchestrator.run_requirement_agent", mock_agent)

    response = await client.post(f"/a2a/{org_id}", json=_send_message("hi"), headers={"X-API-Key": api_key, **_A2A_HEADERS})

    assert response.status_code == 429
    assert "Spend cap exceeded" in response.text
    mock_agent.assert_not_awaited()


async def test_a2a_task_is_rate_limited_per_organization(monkeypatch, client, db_session, register_payload):
    from fastapi import HTTPException, status

    org_id, api_key = await _make_org_with_key(client, db_session, register_payload, ["a2a:call"])
    calls = []

    async def _fake_enforce(key, max_attempts, window_seconds):
        calls.append(key)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts", headers={"Retry-After": "60"})

    monkeypatch.setattr("api.routers.a2a.enforce_rate_limit", _fake_enforce)
    response = await client.post(f"/a2a/{org_id}", json=_send_message("hi"), headers={"X-API-Key": api_key, **_A2A_HEADERS})

    assert response.status_code == 429
    assert f"ratelimit:a2a:org:{org_id}" in calls

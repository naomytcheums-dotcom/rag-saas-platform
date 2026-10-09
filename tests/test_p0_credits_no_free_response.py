"""P0 billing (BILL-008): once the credit balance is reached, no LLM response is ever served for free.

Before the fix, with `0 < balance < cost of the call`, `deduct_credits` refused, the orchestrator swallowed the
`InsufficientCreditsError`, the balance stayed untouched and the answer was served: unlimited unbilled LLM usage.
The LLM provider is always simulated here (`litellm.acompletion` mocked): no real call is ever made."""

import uuid
from unittest.mock import AsyncMock, patch

import litellm
import pytest
from litellm.types.utils import ChatCompletionMessageToolCall, Choices, Function, Message, ModelResponse, Usage
from sqlalchemy import select

from api.config import settings
from api.models.billing import Credit, CreditTransaction, CreditTransactionType
from api.services import agent_orchestrator as ao
from api.services.agent_orchestrator import AgentOrchestrator
from api.services.billing_credits import deduct_credits, deduct_credits_up_to, InsufficientCreditsError

# 500 prompt tokens at 100 tokens per credit = a call that costs exactly 5 credits.
CALL_COST = 5


def _response(text: str = "A simulated answer.", *, prompt_tokens: int = 500, tool_call: bool = False) -> ModelResponse:
    message = Message(content=None if tool_call else text, role="assistant")
    if tool_call:
        message.tool_calls = [ChatCompletionMessageToolCall(id="call_1", type="function", function=Function(name="lookup", arguments="{}"))]
    return ModelResponse(
        choices=[Choices(message=message, index=0, finish_reason="tool_calls" if tool_call else "stop")],
        usage=Usage(prompt_tokens=prompt_tokens, completion_tokens=0, total_tokens=prompt_tokens),
    )


@pytest.fixture(autouse=True)
def _configure_key(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")


async def _fund(db_session, balance: int) -> uuid.UUID:
    org_id = uuid.uuid4()
    db_session.add(Credit(organization_id=org_id, balance=balance))
    await db_session.commit()
    return org_id


async def _balance(db_session, org_id: uuid.UUID) -> int:
    db_session.expire_all()
    return (await db_session.scalar(select(Credit.balance).where(Credit.organization_id == org_id)))


async def _consume_rows(db_session, org_id: uuid.UUID) -> list[CreditTransaction]:
    db_session.expire_all()
    return list((await db_session.scalars(
        select(CreditTransaction).where(CreditTransaction.organization_id == org_id, CreditTransaction.type == CreditTransactionType.consume)
    )).all())


# -- service level ---------------------------------------------------------------------------------------------------

async def test_deduct_credits_up_to_drains_a_balance_smaller_than_the_cost_and_records_the_shortfall(db_session):
    org_id = await _fund(db_session, 1)

    _credit, charged, shortfall = await deduct_credits_up_to(db_session, org_id, CALL_COST, resource_type="llm_call:test")
    await db_session.commit()

    assert (charged, shortfall) == (1, 4)
    assert await _balance(db_session, org_id) == 0  # never negative
    [row] = await _consume_rows(db_session, org_id)
    assert row.amount == -1 and row.balance_after == 0
    assert "4 credits uncollected" in row.reason  # the shortfall is recorded, not silently dropped


async def test_deduct_credits_up_to_on_an_empty_balance_charges_nothing_but_still_records_the_shortfall(db_session):
    org_id = await _fund(db_session, 0)

    _credit, charged, shortfall = await deduct_credits_up_to(db_session, org_id, CALL_COST, resource_type="llm_call:test")
    await db_session.commit()

    assert (charged, shortfall) == (0, CALL_COST)
    assert await _balance(db_session, org_id) == 0
    assert len(await _consume_rows(db_session, org_id)) == 1


async def test_deduct_credits_up_to_with_enough_balance_is_a_normal_full_debit(db_session):
    org_id = await _fund(db_session, 100)

    _credit, charged, shortfall = await deduct_credits_up_to(db_session, org_id, CALL_COST, resource_type="llm_call:test")
    await db_session.commit()

    assert (charged, shortfall) == (CALL_COST, 0)
    assert await _balance(db_session, org_id) == 100 - CALL_COST


async def test_strict_deduct_credits_keeps_its_all_or_nothing_semantics(db_session):
    org_id = await _fund(db_session, 1)

    with pytest.raises(InsufficientCreditsError):
        await deduct_credits(db_session, org_id, CALL_COST, resource_type="a2a_task")

    assert await _balance(db_session, org_id) == 1


# -- orchestrator: run_agent -------------------------------------------------------------------------------------------

async def test_run_agent_with_1_credit_and_a_5_credit_call_drains_the_balance_and_refuses_the_next_call(monkeypatch, db_session):
    llm = AsyncMock(return_value=_response())
    monkeypatch.setattr(litellm, "acompletion", llm)
    org_id = await _fund(db_session, 1)
    orchestrator = AgentOrchestrator()

    first = await orchestrator.run_agent("agent-1", "hi", db=db_session, organization_id=org_id)

    assert first.status == "completed"
    assert llm.await_count == 1
    assert await _balance(db_session, org_id) == 0  # was 1 before the fix (the debit was refused and swallowed)
    [row] = await _consume_rows(db_session, org_id)
    assert row.amount == -1 and "uncollected" in row.reason

    second = await orchestrator.run_agent("agent-1", "again", db=db_session, organization_id=org_id)

    assert second.status == "failed"
    assert "Insufficient AI credits" in second.error
    assert llm.await_count == 1  # the second call never reached the (simulated) provider
    assert await _balance(db_session, org_id) == 0


async def test_run_agent_with_exactly_the_cost_is_billed_in_full_and_the_next_call_is_refused(monkeypatch, db_session):
    llm = AsyncMock(return_value=_response())
    monkeypatch.setattr(litellm, "acompletion", llm)
    org_id = await _fund(db_session, CALL_COST)
    orchestrator = AgentOrchestrator()

    first = await orchestrator.run_agent("agent-1", "hi", db=db_session, organization_id=org_id)
    second = await orchestrator.run_agent("agent-1", "again", db=db_session, organization_id=org_id)

    assert first.status == "completed" and second.status == "failed"
    assert await _balance(db_session, org_id) == 0
    assert llm.await_count == 1


async def test_run_agent_stops_a_tool_loop_once_the_balance_is_exhausted(monkeypatch, db_session):
    """A run that would keep calling the provider (tool-calling loop) after its own debit drained the balance is stopped."""
    llm = AsyncMock(side_effect=[_response(tool_call=True), _response("must never be requested")])
    monkeypatch.setattr(litellm, "acompletion", llm)
    org_id = await _fund(db_session, 1)

    run = await AgentOrchestrator().run_agent("agent-1", "hi", db=db_session, organization_id=org_id)

    assert run.status == "failed"
    assert "Insufficient AI credits" in run.error
    assert llm.await_count == 1
    assert await _balance(db_session, org_id) == 0


async def test_run_agent_debit_failures_are_not_swallowed(monkeypatch, db_session):
    """Only a missing balance is handled (min(balance, cost)); any other failure of the debit propagates instead of being
    logged and ignored."""
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_response()))
    org_id = await _fund(db_session, 100)

    with patch.object(ao, "deduct_credits_up_to", AsyncMock(side_effect=RuntimeError("ledger down"))):
        with pytest.raises(RuntimeError, match="ledger down"):
            await AgentOrchestrator().run_agent("agent-1", "hi", db=db_session, organization_id=org_id)


async def test_run_agent_byok_organization_is_never_debited(monkeypatch, db_session):
    llm = AsyncMock(return_value=_response())
    monkeypatch.setattr(litellm, "acompletion", llm)
    monkeypatch.setattr("api.services.agent_orchestrator.resolve_org_api_key", AsyncMock(return_value="sk-byok-simulated"))
    org_id = await _fund(db_session, 0)

    run = await AgentOrchestrator().run_agent("agent-1", "hi", db=db_session, organization_id=org_id)

    assert run.status == "completed"
    assert await _consume_rows(db_session, org_id) == []


async def test_spend_caps_still_apply_with_partial_debits(monkeypatch, db_session):
    llm = AsyncMock(return_value=_response())
    monkeypatch.setattr(litellm, "acompletion", llm)
    org_id = await _fund(db_session, 1)
    caps = {"daily_credit_limit": 1, "monthly_credit_limit": None}
    orchestrator = AgentOrchestrator()

    await orchestrator.run_agent("agent-1", "hi", db=db_session, organization_id=org_id, org_settings=caps)
    await _fund_top_up(db_session, org_id, 100)  # solvent again, but the 1-credit daily cap was just consumed
    capped = await orchestrator.run_agent("agent-1", "again", db=db_session, organization_id=org_id, org_settings=caps)

    assert capped.status == "failed" and "Spend cap exceeded" in capped.error
    assert llm.await_count == 1


async def _fund_top_up(db_session, org_id: uuid.UUID, amount: int) -> None:
    credit = await db_session.scalar(select(Credit).where(Credit.organization_id == org_id))
    credit.balance += amount
    await db_session.commit()


# -- orchestrator: stream_response -------------------------------------------------------------------------------------

async def test_stream_response_with_1_credit_and_a_5_credit_call_drains_the_balance_and_refuses_the_next_stream(monkeypatch, db_session):
    calls = {"n": 0}

    async def fake_stream(messages, **kwargs):
        calls["n"] += 1
        kwargs["usage_sink"]["prompt_tokens"] = 500
        kwargs["usage_sink"]["completion_tokens"] = 0
        yield "A simulated streamed answer."

    monkeypatch.setattr(ao, "chat_completion_stream_with_tools", fake_stream)
    org_id = await _fund(db_session, 1)
    orchestrator = AgentOrchestrator()

    first = [e async for e in orchestrator.stream_response("agent-1", "hi", db=db_session, organization_id=org_id)]

    assert not any(e["type"] == "error" for e in first), first
    assert calls["n"] == 1
    assert await _balance(db_session, org_id) == 0

    second = [e async for e in orchestrator.stream_response("agent-1", "again", db=db_session, organization_id=org_id)]

    assert any(e["type"] == "error" and "Insufficient AI credits" in e["error"] for e in second)
    assert calls["n"] == 1


# -- voice (same family: the turn debit used to be swallowed) ----------------------------------------------------------

def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _org_with_owner(client, payload) -> tuple[str, str]:
    with patch("api.routers.auth.create_and_send_email_otp", new=AsyncMock()):
        token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    org_id = (await client.post("/organizations", json={"name": "Voice Credits Org"}, headers=_auth(token))).json()["id"]
    return token, org_id


def _audio():
    return {"file": ("q.wav", b"RIFFfakewav", "audio/wav")}


def _simulated_turn():
    return {
        "transcript": "hello", "answer_text": "hi", "answer_audio": None, "response_id": str(uuid.uuid4()), "sources": [],
    }


async def test_voice_turn_below_the_turn_cost_is_refused_before_any_work(client, db_session, register_payload, monkeypatch):
    turn = AsyncMock(return_value=_simulated_turn())
    monkeypatch.setattr("api.routers.voice.voice_agent_turn", turn)
    token, org_id = await _org_with_owner(client, register_payload)
    org_uuid = uuid.UUID(org_id)
    await client.get(f"/organizations/{org_id}/billing/credits", headers=_auth(token))
    credit = await db_session.scalar(select(Credit).where(Credit.organization_id == org_uuid))
    credit.balance = settings.VOICE_AGENT_TURN_CREDIT_COST - 1
    await db_session.commit()

    response = await client.post(f"/voice/organizations/{org_id}/agent", files=_audio(), headers=_auth(token))

    assert response.status_code == 402
    turn.assert_not_awaited()


async def test_voice_turn_racing_the_balance_is_charged_what_is_left_not_served_free(client, db_session, register_payload, monkeypatch):
    token, org_id = await _org_with_owner(client, register_payload)
    org_uuid = uuid.UUID(org_id)
    await client.get(f"/organizations/{org_id}/billing/credits", headers=_auth(token))
    credit = await db_session.scalar(select(Credit).where(Credit.organization_id == org_uuid))
    credit.balance = settings.VOICE_AGENT_TURN_CREDIT_COST
    await db_session.commit()

    async def turn_that_loses_credits_meanwhile(*args, **kwargs):
        # another request drains the balance while this turn is being produced
        row = await db_session.scalar(select(Credit).where(Credit.organization_id == org_uuid))
        row.balance = 4
        await db_session.flush()
        return _simulated_turn()

    monkeypatch.setattr("api.routers.voice.voice_agent_turn", turn_that_loses_credits_meanwhile)

    response = await client.post(f"/voice/organizations/{org_id}/agent", files=_audio(), headers=_auth(token))

    assert response.status_code == 200, response.text
    assert response.json()["credits_charged"] == 4  # was 0 (swallowed) before the fix
    assert await _balance(db_session, org_uuid) == 0

    nxt = await client.post(f"/voice/organizations/{org_id}/agent", files=_audio(), headers=_auth(token))
    assert nxt.status_code == 402

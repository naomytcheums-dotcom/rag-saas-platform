"""Hardening Mission, Phase 13 -- REGRESSION for a real, confirmed cost-
control gap: `api.services.agent_orchestrator`'s own real credit
deduction (`_deduct_for_usage`) only ever runs AFTER a real, already-
incurred LLM call -- by design, documented in its own comment, correct
for THAT call (the real provider cost was already spent). But nothing
ever stopped a NEW run from starting when an organization's real
balance was already at or below zero -- these tests prove the real,
new pre-flight guard closes that gap, for both `run_agent` and
`stream_response`, without ever blocking a real BYOK organization
(billed to their own provider account, never this platform's credits)."""

import uuid
from unittest.mock import AsyncMock

import litellm
import pytest
from litellm.types.utils import Choices, Message, ModelResponse

from api.config import settings
from api.models.billing import Credit
from api.services.agent_orchestrator import AgentOrchestrator


def _real_response(text: str) -> ModelResponse:
    return ModelResponse(choices=[Choices(message=Message(content=text, role="assistant"), index=0, finish_reason="stop")])


@pytest.fixture(autouse=True)
def _configure_key(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")


async def test_run_agent_refuses_to_start_a_new_run_with_a_real_zero_balance(monkeypatch, db_session):
    mock_acompletion = AsyncMock(return_value=_real_response("should never be called"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    org_id = uuid.uuid4()
    db_session.add(Credit(organization_id=org_id, balance=0))
    await db_session.commit()

    orchestrator = AgentOrchestrator()
    run = await orchestrator.run_agent("agent-1", "hi", db=db_session, organization_id=org_id)

    assert run.status == "failed"
    assert "Insufficient AI credits" in run.error
    mock_acompletion.assert_not_awaited()  # the real LLM call must never happen at all


async def test_run_agent_still_runs_normally_with_a_real_positive_balance(monkeypatch, db_session):
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("A real answer.")))

    org_id = uuid.uuid4()
    db_session.add(Credit(organization_id=org_id, balance=1000))
    await db_session.commit()

    orchestrator = AgentOrchestrator()
    run = await orchestrator.run_agent("agent-1", "hi", db=db_session, organization_id=org_id)

    assert run.status == "completed"


async def test_run_agent_skips_the_credit_check_entirely_for_a_real_byok_organization(monkeypatch, db_session):
    """A real, zero-balance organization must still be able to run its
    agents when it configured its own provider key (BYOK) -- the real
    credit check must never apply to a call that isn't billed to this
    platform's own credits at all."""
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("A real answer.")))
    monkeypatch.setattr("api.services.agent_orchestrator.resolve_org_api_key", AsyncMock(return_value="sk-byok-real-key"))

    org_id = uuid.uuid4()
    db_session.add(Credit(organization_id=org_id, balance=0))
    await db_session.commit()

    orchestrator = AgentOrchestrator()
    run = await orchestrator.run_agent("agent-1", "hi", db=db_session, organization_id=org_id)

    assert run.status == "completed"


async def test_stream_response_refuses_to_start_a_new_run_with_a_real_zero_balance(monkeypatch, db_session):
    mock_acompletion = AsyncMock(return_value=_real_response("should never be called"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    org_id = uuid.uuid4()
    db_session.add(Credit(organization_id=org_id, balance=0))
    await db_session.commit()

    orchestrator = AgentOrchestrator()
    events = [event async for event in orchestrator.stream_response("agent-1", "hi", db=db_session, organization_id=org_id)]

    assert any(e["type"] == "error" and "Insufficient AI credits" in e["error"] for e in events)
    mock_acompletion.assert_not_awaited()


async def test_run_agent_refuses_to_start_a_new_run_once_the_real_daily_spend_cap_is_reached(monkeypatch, db_session):
    """Hardening Mission, §6 (cost control) -- the real, organization-
    configured `daily_credit_limit` must stop a new run even though the
    organization still has a real, positive `Credit.balance` (distinct
    from insolvency, see billing_credits.py's own enforce_spend_caps
    docstring)."""
    import datetime as dt

    from api.models.billing import CreditTransaction, CreditTransactionType

    mock_acompletion = AsyncMock(return_value=_real_response("should never be called"))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    org_id = uuid.uuid4()
    db_session.add(Credit(organization_id=org_id, balance=10_000))
    db_session.add(CreditTransaction(
        organization_id=org_id, type=CreditTransactionType.consume, amount=-500,
        balance_after=9_500, reason="llm_call:test", created_at=dt.datetime.now(dt.timezone.utc),
    ))
    await db_session.commit()

    orchestrator = AgentOrchestrator()
    run = await orchestrator.run_agent(
        "agent-1", "hi", db=db_session, organization_id=org_id, org_settings={"daily_credit_limit": 500, "monthly_credit_limit": None},
    )

    assert run.status == "failed"
    assert "Spend cap exceeded" in run.error
    mock_acompletion.assert_not_awaited()


async def test_run_agent_still_runs_normally_under_a_real_unreached_daily_spend_cap(monkeypatch, db_session):
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("A real answer.")))

    org_id = uuid.uuid4()
    db_session.add(Credit(organization_id=org_id, balance=1000))
    await db_session.commit()

    orchestrator = AgentOrchestrator()
    run = await orchestrator.run_agent(
        "agent-1", "hi", db=db_session, organization_id=org_id, org_settings={"daily_credit_limit": 999_999, "monthly_credit_limit": None},
    )

    assert run.status == "completed"

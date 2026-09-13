"""Partie 23 (cost tracking finalization) -- real, per-step and
per-agent USD cost accumulation, reusing
api.services.cost_tracking.calculate_cost_per_request's own real,
static pricing table and chat_completion_with_usage's own real,
provider-reported token usage (both Partie 7.2.14/7.2.15, unchanged)."""

import json
import uuid
from unittest.mock import AsyncMock

import pytest
from litellm.types.utils import Choices, Message, ModelResponse, Usage
from sqlalchemy import select

from api.config import settings
from api.models.autonomous_agent import AgentPlan, AgentStep, AgentStepStatus, AutonomousAgent, AutonomousAgentStatus
from api.models.user import User
from api.services import autonomous_agents as service


def _real_completion_response(text: str, prompt_tokens: int = 0, completion_tokens: int = 0) -> ModelResponse:
    message = Message(content=text, role="assistant")
    choice = Choices(message=message, index=0, finish_reason="stop")
    response = ModelResponse(choices=[choice])
    if prompt_tokens or completion_tokens:
        response.usage = Usage(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=prompt_tokens + completion_tokens)
        response.model = "claude-3-5-sonnet-20241022"  # matches the real COST_MODEL_PRICING substring key
    return response


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _make_org(client, db_session, register_payload, name):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_id = (await client.post("/organizations", json={"name": name}, headers=_auth_header(owner_token))).json()["id"]
    return owner_token, org_id


async def _make_agent(db_session, org_id, **kwargs) -> AutonomousAgent:
    agent = AutonomousAgent(organization_id=uuid.UUID(org_id), name="A", goal="A real goal", **kwargs)
    db_session.add(agent)
    await db_session.flush()
    return agent


async def _make_plan_with_step(db_session, agent, description: str) -> tuple[AgentPlan, AgentStep]:
    plan = AgentPlan(agent_id=agent.id, goal=agent.goal, steps=[{"description": description, "depends_on": []}])
    db_session.add(plan)
    await db_session.flush()
    step = AgentStep(plan_id=plan.id, step_number=1, action="pending", parameters={"description": description})
    db_session.add(step)
    await db_session.flush()
    return plan, step


@pytest.fixture(autouse=True)
def _configure_llm_key(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")


async def test_execute_step_accumulates_real_cost_on_step_and_agent(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr(settings, "TOOL_SELECTION_USE_LLM", False)
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Cost Org")
    agent = await _make_agent(db_session, org_id)
    # Deliberately no real keyword overlap with the calculator/word_count
    # tools' own name/description/tags (a real, found bug: "Summarize
    # the real findings" scored exactly 0.5 -- AT the real
    # TOOL_SELECTION_THRESHOLD -- purely from "the"/"real" both
    # incidentally appearing in word_count's own description text,
    # wrongly selecting it over the intended reasoning fallback).
    _plan, step = await _make_plan_with_step(db_session, agent, "Draft product announcement copy")
    await db_session.commit()

    import litellm

    # Real Claude 3.5 Sonnet pricing: $3/M input, $15/M output -- 1000
    # prompt + 500 completion tokens = real $0.003 + $0.0075 = $0.0105.
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_completion_response(
        "A real summary.", prompt_tokens=1000, completion_tokens=500,
    )))

    updated = await service.execute_step(db_session, step, agent)
    await db_session.commit()

    assert updated.status == AgentStepStatus.completed.value
    assert float(updated.total_cost) == pytest.approx(0.0105, rel=1e-3)
    assert float(agent.total_cost) == pytest.approx(0.0105, rel=1e-3)


async def test_get_agent_cost_endpoint_returns_real_total_and_breakdown(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr(settings, "TOOL_SELECTION_USE_LLM", False)
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Cost Endpoint Org")
    agent = await _make_agent(db_session, org_id)
    _plan, step = await _make_plan_with_step(db_session, agent, "Real reasoning step")
    await db_session.commit()

    import litellm

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_completion_response(
        "Done.", prompt_tokens=1000, completion_tokens=1000,
    )))
    await service.execute_step(db_session, step, agent)
    await db_session.commit()

    response = await client.get(f"/autonomous-agents/{agent.id}/cost", headers=_auth_header(owner_token))
    assert response.status_code == 200
    body = response.json()
    assert body["total_cost"] == pytest.approx(0.018, rel=1e-3)  # 1000*3/1e6 + 1000*15/1e6
    assert body["currency"] == "USD"
    assert len(body["steps"]) == 1
    assert body["steps"][0]["cost"] == pytest.approx(0.018, rel=1e-3)


async def test_run_autonomous_agent_pauses_when_max_cost_exceeded(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr(settings, "TOOL_SELECTION_USE_LLM", False)
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Max Cost Org")
    # A real, tiny per-agent cost cap -- one real, cheap step will already exceed it.
    agent = await _make_agent(db_session, org_id, guardrails={"max_cost": 0.001})
    await db_session.commit()

    import litellm

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(side_effect=[
        _real_completion_response(json.dumps([
            {"description": "Step one", "depends_on": []}, {"description": "Step two", "depends_on": [0]},
        ])),
        _real_completion_response("Result of step one.", prompt_tokens=1000, completion_tokens=1000),  # real $0.018, already over the $0.001 cap
    ]))

    updated = await service.run_autonomous_agent(db_session, agent.id)
    await db_session.commit()

    assert updated.status == AutonomousAgentStatus.paused.value
    assert updated.current_step == 1  # the real, first (over-budget) step still ran and was recorded; the SECOND step never started


async def test_check_guardrails_flags_an_already_exceeded_cost_budget():
    agent = AutonomousAgent(organization_id=uuid.uuid4(), name="A", goal="G", guardrails={"max_cost": 0.01}, total_cost=0.02)
    result = service.check_guardrails(agent, "any real action")
    assert result["passed"] is False
    assert any("max_cost_exceeded" in v for v in result["violations"])


async def test_enforce_limits_respects_the_real_global_default_when_no_per_agent_override(monkeypatch):
    monkeypatch.setattr(settings, "AUTONOMOUS_MAX_COST", 5.0)
    agent = AutonomousAgent(organization_id=uuid.uuid4(), name="A", goal="G", max_steps=100, current_step=0, total_cost=4.0)
    step = AgentStep(plan_id=uuid.uuid4(), step_number=1, action="pending")
    assert service.enforce_limits(agent, step) is True

    agent.total_cost = 5.0
    assert service.enforce_limits(agent, step) is False

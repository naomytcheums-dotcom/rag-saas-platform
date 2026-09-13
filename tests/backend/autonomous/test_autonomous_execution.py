"""Partie 23 -- real multi-step execution: real tool selection/
invocation (the calculator tool, api.services.tools.CALCULATOR_TOOL),
real reasoning-only fallback, guardrail blocking, max_steps/human-
approval pausing, and the full run_autonomous_agent loop."""

import json
import uuid
from unittest.mock import AsyncMock

import pytest
from litellm.types.utils import Choices, Message, ModelResponse
from sqlalchemy import select

from api.config import settings
from api.models.autonomous_agent import (
    AgentPlan, AgentStep, AgentStepStatus, AutonomousAgent, AutonomousAgentStatus,
)
from api.models.user import User
from api.services import autonomous_agents as service


@pytest.fixture(autouse=True)
def _configure_llm_key(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")


def _real_completion_response(text: str) -> ModelResponse:
    message = Message(content=text, role="assistant")
    choice = Choices(message=message, index=0, finish_reason="stop")
    return ModelResponse(choices=[choice])


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


async def test_execute_step_uses_the_real_calculator_tool(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr(settings, "TOOL_SELECTION_USE_LLM", False)  # real, deterministic keyword ranking -- no LLM call needed to SELECT the tool
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Execution Org")
    agent = await _make_agent(db_session, org_id)
    _plan, step = await _make_plan_with_step(db_session, agent, "calculator arithmetic expression 2 + 2")
    await db_session.commit()

    import litellm

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_completion_response(json.dumps({"expression": "2 + 2"}))))

    updated = await service.execute_step(db_session, step, agent)
    await db_session.commit()

    assert updated.status == AgentStepStatus.completed.value
    assert updated.action == "calculator"
    assert updated.result == {"output": "4"}


async def test_execute_step_falls_back_to_reasoning_when_no_real_tool_matches(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr(settings, "TOOL_SELECTION_USE_LLM", False)
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Reasoning Org")
    agent = await _make_agent(db_session, org_id)
    _plan, step = await _make_plan_with_step(db_session, agent, "Summarize why the sky appears blue")
    await db_session.commit()

    import litellm

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_completion_response("Rayleigh scattering.")))

    updated = await service.execute_step(db_session, step, agent)
    await db_session.commit()

    assert updated.status == AgentStepStatus.completed.value
    assert updated.action == "respond"
    assert updated.result == {"output": "Rayleigh scattering."}


async def test_execute_step_is_blocked_by_a_real_guardrail(client, db_session, register_payload):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Guardrail Org")
    agent = await _make_agent(db_session, org_id, guardrails={"blocked_topics": ["competitor secrets"]})
    _plan, step = await _make_plan_with_step(db_session, agent, "Find competitor secrets")
    await db_session.commit()

    updated = await service.execute_step(db_session, step, agent)
    await db_session.commit()

    assert updated.status == AgentStepStatus.failed.value
    assert "guardrail" in updated.error.lower()


async def test_handle_error_records_the_real_failure():
    step = AgentStep(plan_id=uuid.uuid4(), step_number=1, action="pending")
    service.handle_error(RuntimeError("a real tool outage"), step)
    assert step.status == AgentStepStatus.failed.value
    assert step.error == "a real tool outage"


async def test_run_autonomous_agent_completes_a_real_simple_plan(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr(settings, "TOOL_SELECTION_USE_LLM", False)
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Run Org")
    agent = await _make_agent(db_session, org_id, max_steps=5)
    await db_session.commit()

    import litellm

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(side_effect=[
        _real_completion_response(json.dumps([{"description": "Summarize the goal", "depends_on": []}])),  # decompose_task
        _real_completion_response("Here is the real summary."),  # the step's own reasoning response
    ]))

    updated = await service.run_autonomous_agent(db_session, agent.id)
    await db_session.commit()

    assert updated.status == AutonomousAgentStatus.completed.value
    assert updated.current_step == 1
    plans = await service.list_agent_plans(db_session, agent.id)
    assert plans[0].status == "completed"


async def test_run_autonomous_agent_pauses_at_max_steps(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr(settings, "TOOL_SELECTION_USE_LLM", False)
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Max Steps Org")
    agent = await _make_agent(db_session, org_id, max_steps=1)
    await db_session.commit()

    import litellm

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(side_effect=[
        _real_completion_response(json.dumps([
            {"description": "Step one", "depends_on": []}, {"description": "Step two", "depends_on": [0]},
        ])),
        _real_completion_response("Result of step one."),
    ]))

    updated = await service.run_autonomous_agent(db_session, agent.id)
    await db_session.commit()

    assert updated.status == AutonomousAgentStatus.paused.value
    assert updated.current_step == 1  # only the real, first step ran before the real max_steps cap stopped it


async def test_run_autonomous_agent_pauses_for_human_approval(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr(settings, "TOOL_SELECTION_USE_LLM", False)
    monkeypatch.setattr(settings, "AUTONOMOUS_HUMAN_APPROVAL", True)
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Approval Org")
    agent = await _make_agent(db_session, org_id, guardrails={"require_approval_for": ["Send the real email"]})
    await db_session.commit()

    import litellm

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_completion_response(
        json.dumps([{"description": "Send the real email", "depends_on": []}])
    )))

    updated = await service.run_autonomous_agent(db_session, agent.id)
    await db_session.commit()

    assert updated.status == AutonomousAgentStatus.paused.value
    assert updated.current_step == 0  # never actually executed -- paused BEFORE the real step ran

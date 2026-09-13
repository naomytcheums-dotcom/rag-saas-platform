"""Partie 23 -- real planning: create_agent_plan/validate_plan/
replan_if_needed, reusing api.services.task_planning.decompose_task
(mocked at the same real litellm.acompletion boundary
tests/test_task_planning.py itself already mocks)."""

import json
import uuid
from unittest.mock import AsyncMock

import pytest
from litellm.types.utils import Choices, Message, ModelResponse
from sqlalchemy import select

from api.config import settings
from api.models.autonomous_agent import AgentPlanStatus, AgentStepStatus, AutonomousAgent, AutonomousAgentStatus
from api.models.user import User
from api.services import autonomous_agents as service


@pytest.fixture(autouse=True)
def _configure_llm_key(monkeypatch):
    # Real, required boundary: chat_completion (and so decompose_task)
    # checks for a real provider API key BEFORE ever reaching the
    # mocked litellm.acompletion call below -- same real
    # "_configure_keys" precedent as tests/test_llm_providers.py's own
    # autouse fixture.
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


def test_validate_plan_rejects_a_real_dependency_cycle():
    steps = [{"description": "a", "depends_on": [1]}, {"description": "b", "depends_on": [0]}]
    errors = service.validate_plan(steps)
    assert any("cycle" in e for e in errors)


def test_validate_plan_accepts_a_real_linear_plan():
    steps = [{"description": "a", "depends_on": []}, {"description": "b", "depends_on": [0]}]
    assert service.validate_plan(steps) == []


async def test_create_agent_plan_persists_real_steps(client, db_session, register_payload, monkeypatch):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Plan Org")
    agent = AutonomousAgent(organization_id=uuid.UUID(org_id), name="A", goal="Write a real report", max_steps=10)
    db_session.add(agent)
    await db_session.commit()

    import litellm

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_completion_response(
        json.dumps([{"description": "Research the topic", "depends_on": []}, {"description": "Write the report", "depends_on": [0]}])
    )))

    plan = await service.create_agent_plan(db_session, agent)
    await db_session.commit()

    assert plan.status == AgentPlanStatus.pending.value
    assert len(plan.steps) == 2
    steps = await service.list_agent_steps(db_session, plan.id)
    assert [s.step_number for s in steps] == [1, 2]
    assert all(s.status == AgentStepStatus.pending.value for s in steps)


async def test_create_agent_plan_persists_a_real_plan_longer_than_max_steps(client, db_session, register_payload, monkeypatch):
    """Real, deliberate design: a plan longer than this agent's own
    `max_steps` is NOT rejected outright at creation -- the real
    execution loop's own `enforce_limits` pauses the agent once the
    real cap is reached (see test_autonomous_execution.py's own
    `test_run_autonomous_agent_pauses_at_max_steps`), letting a real,
    open-ended goal still make real partial progress rather than
    refusing to start."""
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Too Many Steps Org")
    agent = AutonomousAgent(organization_id=uuid.UUID(org_id), name="A", goal="Do a lot", max_steps=1)
    db_session.add(agent)
    await db_session.commit()

    import litellm

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_completion_response(
        json.dumps([{"description": "step 1", "depends_on": []}, {"description": "step 2", "depends_on": [0]}])
    )))

    plan = await service.create_agent_plan(db_session, agent)
    await db_session.commit()

    assert plan.status == AgentPlanStatus.pending.value
    assert len(await service.list_agent_steps(db_session, plan.id)) == 2


async def test_replan_if_needed_regenerates_only_the_real_remaining_steps(client, db_session, register_payload, monkeypatch):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Replan Org")
    agent = AutonomousAgent(organization_id=uuid.UUID(org_id), name="A", goal="A real goal", max_steps=10)
    db_session.add(agent)
    await db_session.commit()

    import litellm

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_completion_response(
        json.dumps([{"description": "step 1", "depends_on": []}, {"description": "step 2", "depends_on": [0]}, {"description": "step 3", "depends_on": [1]}])
    )))
    plan = await service.create_agent_plan(db_session, agent)
    await db_session.commit()

    steps = await service.list_agent_steps(db_session, plan.id)
    failed_step = steps[0]
    failed_step.status = AgentStepStatus.failed.value
    failed_step.error = "a real tool failure"
    await db_session.commit()

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_completion_response(
        json.dumps([{"description": "recovered step", "depends_on": []}])
    )))
    await service.replan_if_needed(db_session, plan, failed_step)
    await db_session.commit()

    remaining = await service.list_agent_steps(db_session, plan.id)
    descriptions = [(s.parameters or {}).get("description") for s in remaining]
    assert "recovered step" in descriptions
    assert "step 2" not in descriptions  # the real, stale remaining steps were replaced

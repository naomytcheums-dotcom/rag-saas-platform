"""Partie 23 -- real agent-to-agent collaboration: request/accept/
execute, and shared-context delivery into the collaborator's own real
short-term memory."""

import uuid
from unittest.mock import AsyncMock

import pytest
from litellm.types.utils import Choices, Message, ModelResponse
from sqlalchemy import select

from api.config import settings
from api.models.autonomous_agent import AgentCollaborationStatus, AgentMemoryType, AutonomousAgent
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


async def _make_agent(db_session, org_id, goal="A real goal") -> AutonomousAgent:
    agent = AutonomousAgent(organization_id=uuid.UUID(org_id), name="A", goal=goal)
    db_session.add(agent)
    await db_session.flush()
    return agent


async def test_collaborate_endpoint_runs_a_real_collaboration_end_to_end(client, db_session, register_payload, monkeypatch):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Collab Org")
    initiator = await _make_agent(db_session, org_id, goal="Plan a real launch")
    collaborator = await _make_agent(db_session, org_id, goal="Review real copy for tone")
    await db_session.commit()

    import litellm

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_completion_response("The real tone looks good.")))

    response = await client.post(
        f"/autonomous-agents/{initiator.id}/collaborate",
        json={"collaborator_agent_id": str(collaborator.id), "task": "Review this real launch copy"},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "completed"
    assert body["result"]["output"] == "The real tone looks good."


async def test_execute_collaboration_marks_failed_on_a_real_llm_error(client, db_session, register_payload, monkeypatch):
    from api.services.llm_providers import LLMProviderError

    owner_token, org_id = await _make_org(client, db_session, register_payload, "Collab Fail Org")
    initiator = await _make_agent(db_session, org_id)
    collaborator = await _make_agent(db_session, org_id)
    await db_session.commit()

    collaboration = await service.request_collaboration(db_session, initiator.id, collaborator.id, "A real task")
    await db_session.commit()

    import litellm

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(side_effect=LLMProviderError("real provider outage")))

    updated = await service.execute_collaboration(db_session, collaboration.id)
    await db_session.commit()

    assert updated.status == AgentCollaborationStatus.failed.value
    assert "real provider outage" in updated.result["error"]


async def test_list_collaborations_includes_both_initiator_and_collaborator_roles(client, db_session, register_payload):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "List Collab Org")
    agent_a = await _make_agent(db_session, org_id)
    agent_b = await _make_agent(db_session, org_id)
    await db_session.commit()

    await service.request_collaboration(db_session, agent_a.id, agent_b.id, "A asks B")
    await service.request_collaboration(db_session, agent_b.id, agent_a.id, "B asks A")
    await db_session.commit()

    response = await client.get(f"/autonomous-agents/{agent_a.id}/collaborations", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert len(response.json()) == 2  # real, both directions


async def test_share_context_writes_into_the_collaborators_own_short_term_memory(client, db_session, register_payload):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Share Context Org")
    initiator = await _make_agent(db_session, org_id)
    collaborator = await _make_agent(db_session, org_id)
    await db_session.commit()

    await service.share_context(db_session, initiator.id, collaborator.id, "The real deadline is tomorrow.")
    await db_session.commit()

    memories = await service.get_agent_memory(db_session, collaborator.id, AgentMemoryType.short_term.value)
    assert len(memories) == 1
    assert "real deadline" in memories[0].content

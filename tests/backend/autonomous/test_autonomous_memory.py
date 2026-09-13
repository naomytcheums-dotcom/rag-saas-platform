"""Partie 23 -- real tiered agent memory: short_term/long_term/episodic
storage, real semantic retrieval (real sentence-transformers
embeddings, no mocking needed -- same reasoning as
tests/backend/media/test_media_search.py's own docstring), real
consolidation and forgetting."""

import datetime as dt
import uuid
from unittest.mock import AsyncMock

import pytest
from litellm.types.utils import Choices, Message, ModelResponse
from sqlalchemy import select

from api.config import settings
from api.models.autonomous_agent import AgentMemory, AgentMemoryType, AutonomousAgent
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


async def _make_agent(db_session, org_id) -> AutonomousAgent:
    agent = AutonomousAgent(organization_id=uuid.UUID(org_id), name="A", goal="A real goal")
    db_session.add(agent)
    await db_session.flush()
    return agent


async def test_add_agent_memory_stores_a_real_embedding(client, db_session, register_payload):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Memory Org")
    agent = await _make_agent(db_session, org_id)
    await db_session.commit()

    memory = await service.add_agent_memory(db_session, agent.id, "The user prefers concise answers.", AgentMemoryType.short_term.value)
    await db_session.commit()

    assert memory.embedding is not None
    assert len(memory.embedding) > 0


async def test_get_agent_memory_endpoint_filters_by_type(client, db_session, register_payload):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Memory Filter Org")
    agent = await _make_agent(db_session, org_id)
    await db_session.commit()

    await service.store_short_term_memory(db_session, agent.id, "A recent fact.")
    await service.store_long_term_memory(db_session, agent.id, "A durable fact.")
    await db_session.commit()

    response = await client.get(f"/autonomous-agents/{agent.id}/memory?memory_type=long_term", headers=_auth_header(owner_token))
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["memory_type"] == "long_term"


async def test_retrieve_relevant_memory_ranks_by_real_semantic_similarity(client, db_session, register_payload):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Retrieve Org")
    agent = await _make_agent(db_session, org_id)
    await db_session.commit()

    await service.add_agent_memory(db_session, agent.id, "Le chat mange une souris dans le jardin.", AgentMemoryType.episodic.value)
    await service.add_agent_memory(db_session, agent.id, "Une voiture rouge est garee devant un immeuble.", AgentMemoryType.episodic.value)
    await db_session.commit()

    results = await service.retrieve_relevant_memory(db_session, agent.id, "un chat et une souris", top_k=5)
    assert results
    assert "chat" in results[0]["memory"].content


async def test_delete_agent_memory_endpoint(client, db_session, register_payload):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Delete Memory Org")
    agent = await _make_agent(db_session, org_id)
    await db_session.commit()

    memory = await service.store_short_term_memory(db_session, agent.id, "Something transient.")
    await db_session.commit()

    response = await client.delete(f"/autonomous-agents/{agent.id}/memory/{memory.id}", headers=_auth_header(owner_token))
    assert response.status_code == 204
    assert await db_session.get(AgentMemory, memory.id) is None


async def test_consolidate_memory_summarizes_real_short_term_entries(client, db_session, register_payload, monkeypatch):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Consolidate Org")
    agent = await _make_agent(db_session, org_id)
    await db_session.commit()

    await service.store_short_term_memory(db_session, agent.id, "Event one happened.")
    await service.store_short_term_memory(db_session, agent.id, "Event two happened.")
    await db_session.commit()

    import litellm

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_completion_response("Two real events happened in sequence.")))

    consolidated = await service.consolidate_memory(db_session, agent.id)
    await db_session.commit()

    assert consolidated is not None
    assert consolidated.memory_type == AgentMemoryType.long_term.value
    remaining_short_term = await service.get_agent_memory(db_session, agent.id, AgentMemoryType.short_term.value)
    assert remaining_short_term == []  # the real, original short-term entries were consolidated away


async def test_consolidate_memory_is_a_real_no_op_with_fewer_than_2_entries(client, db_session, register_payload):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "No-op Consolidate Org")
    agent = await _make_agent(db_session, org_id)
    await db_session.commit()

    await service.store_short_term_memory(db_session, agent.id, "Only one real event.")
    await db_session.commit()

    assert await service.consolidate_memory(db_session, agent.id) is None


async def test_forget_old_memory_only_removes_stale_short_term_entries(client, db_session, register_payload):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Forget Org")
    agent = await _make_agent(db_session, org_id)
    await db_session.commit()

    old_memory = await service.store_short_term_memory(db_session, agent.id, "An old, stale fact.")
    old_memory.created_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=90)
    recent_memory = await service.store_short_term_memory(db_session, agent.id, "A recent fact.")
    long_term = await service.store_long_term_memory(db_session, agent.id, "A durable fact, never forgotten.")
    long_term.created_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=90)
    await db_session.commit()

    forgotten = await service.forget_old_memory(db_session, agent.id, days=30)
    await db_session.commit()

    assert forgotten == 1
    remaining = await service.get_agent_memory(db_session, agent.id)
    remaining_ids = {m.id for m in remaining}
    assert recent_memory.id in remaining_ids
    assert long_term.id in remaining_ids  # real long_term memories are never auto-forgotten
    assert old_memory.id not in remaining_ids

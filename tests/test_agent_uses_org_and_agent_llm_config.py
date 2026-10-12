"""E2E finding 2026-10-12: the agent runtime ignored the organization's LLM settings and the agent's own model / prompt (always the global default
provider). The LLM boundary (`litellm.acompletion`) is mocked here ONLY to capture what the product asks it to call; the E2E journey
(scripts/e2e_full_journey.py) proves the same behaviour against a real Ollama server."""

import uuid
from unittest.mock import AsyncMock

import litellm
import pytest
from litellm.types.utils import Choices, Message, ModelResponse

from api.config import settings
from api.models.organization import OrganizationMember, OrganizationRole
from api.security.agents import create_agent
from api.security.organization_settings import update_org_settings
from api.services.agent_orchestrator import AgentOrchestrator


def _response(text="ok") -> ModelResponse:
    return ModelResponse(choices=[Choices(message=Message(content=text, role="assistant"), index=0, finish_reason="stop")])


@pytest.fixture(autouse=True)
def _keys(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr(settings, "OLLAMA_BASE_URL", "http://127.0.0.1:11434")


async def _org_with_member(db_session):
    org_id, user_id = uuid.uuid4(), uuid.uuid4()
    db_session.add(OrganizationMember(organization_id=org_id, user_id=user_id, role=OrganizationRole.owner))
    await db_session.commit()
    return org_id, user_id


async def test_run_agent_uses_the_organization_llm_settings(monkeypatch, db_session):
    mock = AsyncMock(return_value=_response())
    monkeypatch.setattr(litellm, "acompletion", mock)
    org_id, user_id = await _org_with_member(db_session)
    await update_org_settings(db_session, org_id, {"llm_provider": "ollama", "llm_model": "qwen2.5:7b", "temperature": 0.1})
    agent = await create_agent(db_session, org_id, {"name": "Bot", "is_public": True}, None)
    await db_session.commit()

    run = await AgentOrchestrator().run_agent(str(agent.id), "hi", db=db_session, organization_id=org_id, created_by=user_id)

    assert run.status == "completed", run.error
    kwargs = mock.call_args.kwargs
    assert kwargs["model"].startswith("ollama/") and "qwen2.5:7b" in kwargs["model"]
    assert kwargs["temperature"] == 0.1


async def test_run_agent_uses_the_agents_own_model_and_prompt_over_the_organization(monkeypatch, db_session):
    mock = AsyncMock(return_value=_response())
    monkeypatch.setattr(litellm, "acompletion", mock)
    org_id, user_id = await _org_with_member(db_session)
    await update_org_settings(db_session, org_id, {"llm_provider": "anthropic"})
    agent = await create_agent(db_session, org_id, {
        "name": "Bot", "is_public": True, "system_prompt": "You are the Zorblax pirate assistant.",
        "model_config": {"provider": "ollama", "model": "qwen2.5:3b", "temperature": 0.3}}, None)
    await db_session.commit()

    await AgentOrchestrator().run_agent(str(agent.id), "hi", db=db_session, organization_id=org_id, created_by=user_id)

    kwargs = mock.call_args.kwargs
    assert "qwen2.5:3b" in kwargs["model"] and kwargs["temperature"] == 0.3
    assert "Zorblax pirate" in kwargs["messages"][0]["content"]


async def test_an_agent_with_the_default_prompt_keeps_the_organization_prompt(monkeypatch, db_session):
    mock = AsyncMock(return_value=_response())
    monkeypatch.setattr(litellm, "acompletion", mock)
    org_id, user_id = await _org_with_member(db_session)
    await update_org_settings(db_session, org_id, {"system_prompt": "Organization house style: be terse."})
    agent = await create_agent(db_session, org_id, {"name": "Bot", "is_public": True}, None)
    await db_session.commit()

    await AgentOrchestrator().run_agent(str(agent.id), "hi", db=db_session, organization_id=org_id, created_by=user_id)

    assert "Organization house style" in mock.call_args.kwargs["messages"][0]["content"]


async def test_explicit_caller_overrides_still_win(monkeypatch, db_session):
    mock = AsyncMock(return_value=_response())
    monkeypatch.setattr(litellm, "acompletion", mock)
    org_id, user_id = await _org_with_member(db_session)
    await update_org_settings(db_session, org_id, {"llm_provider": "ollama", "llm_model": "qwen2.5:7b"})
    agent = await create_agent(db_session, org_id, {"name": "Bot", "is_public": True}, None)
    await db_session.commit()

    await AgentOrchestrator().run_agent(str(agent.id), "hi", db=db_session, organization_id=org_id, created_by=user_id,
                                        llm_overrides={"provider": "anthropic", "model": settings.ANTHROPIC_MODEL})

    assert mock.call_args.kwargs["model"] == settings.ANTHROPIC_MODEL


async def test_stream_response_uses_the_organization_llm_settings(monkeypatch, db_session):
    captured = {}

    async def fake_stream(messages, **kwargs):
        captured.update(kwargs)
        yield "hello"

    monkeypatch.setattr("api.services.agent_orchestrator.chat_completion_stream_with_tools", fake_stream)
    org_id, user_id = await _org_with_member(db_session)
    await update_org_settings(db_session, org_id, {"llm_provider": "ollama", "llm_model": "qwen2.5:7b"})
    agent = await create_agent(db_session, org_id, {"name": "Bot", "is_public": True}, None)
    await db_session.commit()

    events = [e async for e in AgentOrchestrator().stream_response(str(agent.id), "hi", db=db_session, organization_id=org_id, created_by=user_id)]

    assert not [e for e in events if e.get("type") == "error"], events
    assert captured.get("provider") == "ollama" and "qwen2.5:7b" in str(captured.get("model"))

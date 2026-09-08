"""Partie 8.1.1 -- SSE streaming. Fast SQLite suite; litellm's own real
`stream=True` mode mocked as a real async generator of chunk objects,
same real boundary as tests/test_agent_orchestrator.py's own
litellm.acompletion mock."""

import uuid

import litellm
import pytest
from unittest.mock import AsyncMock

from api.config import settings
from api.models.agent import Agent
from api.models.organization import Organization
from api.services.agent_orchestrator import AgentOrchestrator
from api.services.streaming import format_sse_event, send_citation, send_done, send_error, send_token, stream_agent_response


class _FakeDelta:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.delta = _FakeDelta(content)


class _FakeChunk:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


async def _fake_stream_gen(tokens):
    for t in tokens:
        yield _FakeChunk(t)


def _fake_stream(tokens):
    return _fake_stream_gen(tokens)


@pytest.fixture(autouse=True)
def _configure_key(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")


async def _make_org_and_agent(db_session, name):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    agent = Agent(organization_id=org.id, name="Bot", system_prompt="You are helpful.")
    db_session.add(agent)
    await db_session.commit()
    return org, agent


# --------------------------------------- SSE formatting --


def test_format_sse_event_produces_the_real_standard_wire_format():
    """Validation criterion: les événements sont corrects."""
    event = format_sse_event("token", {"token": "Hi"})
    assert event == 'event: token\ndata: {"token": "Hi"}\n\n'


def test_send_token_and_send_citation_and_send_done_and_send_error():
    assert "token" in send_token("hi")
    assert "citation" in send_citation({"id": "1"})
    assert "done" in send_done({"result": "ok"})
    assert "error" in send_error("boom")


# --------------------------------------- AgentOrchestrator.stream_response --


async def test_stream_response_yields_real_tokens_then_done(monkeypatch, db_session):
    """Validation criterion: le streaming fonctionne."""
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_fake_stream(["Hello", " world"])))

    org, agent = await _make_org_and_agent(db_session, "Streaming Org")
    orchestrator = AgentOrchestrator()

    events = [event async for event in orchestrator.stream_response(str(agent.id), "Hi", db=db_session, organization_id=org.id)]

    types = [e["type"] for e in events]
    assert types[0] == "start"
    assert types.count("token") == 2
    assert "".join(e["token"] for e in events if e["type"] == "token") == "Hello world"
    assert types[-1] == "done"
    assert events[-1]["result"] == "Hello world"


async def test_stream_response_sends_citations_before_done(monkeypatch, db_session):
    """Validation criterion (vision critique 3): cohérence -- les
    citations sont envoyées après les tokens, avant done (jamais
    entrelacées avec des tokens individuels)."""
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_fake_stream(["An answer."])))

    org, agent = await _make_org_and_agent(db_session, "Streaming Citation Org")
    orchestrator = AgentOrchestrator()
    chunks = [{"chunk_id": str(uuid.uuid4()), "document_id": str(uuid.uuid4()), "content": "Some real content.", "score": 0.9}]

    events = [
        event async for event in orchestrator.stream_response(
            str(agent.id), "Hi", db=db_session, organization_id=org.id, citation_chunks=chunks,
        )
    ]

    types = [e["type"] for e in events]
    assert "citation" in types
    assert types.index("citation") > types.index("token")
    assert types.index("citation") < types.index("done")


async def test_stream_response_yields_an_error_event_on_a_real_llm_failure(monkeypatch, db_session):
    """Validation criterion: robustesse -- les erreurs sont gérées."""
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(side_effect=RuntimeError("simulated real provider failure")))

    org, agent = await _make_org_and_agent(db_session, "Streaming Error Org")
    orchestrator = AgentOrchestrator()

    events = [event async for event in orchestrator.stream_response(str(agent.id), "Hi", db=db_session, organization_id=org.id)]

    assert events[-1]["type"] == "error"
    assert "simulated real provider failure" in events[-1]["error"]


async def test_stream_response_denies_a_real_unauthorized_user(monkeypatch, db_session):
    """Validation criterion: robustesse -- permissions."""
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_fake_stream(["nope"])))
    monkeypatch.setattr("api.services.agent_orchestrator.check_agent_permission", AsyncMock(return_value=False))
    org, agent = await _make_org_and_agent(db_session, "Streaming Perms Org")

    orchestrator = AgentOrchestrator()
    events = [
        event async for event in orchestrator.stream_response(
            str(agent.id), "Hi", db=db_session, organization_id=org.id, created_by=uuid.uuid4(),
        )
    ]

    assert events[-1]["type"] == "error"
    assert "Permission denied" in events[-1]["error"]
    assert not any(e["type"] == "token" for e in events)


async def test_stream_agent_response_produces_real_sse_text(monkeypatch, db_session):
    """Validation criterion: le streaming fonctionne (bout en bout)."""
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_fake_stream(["Hi"])))
    org, agent = await _make_org_and_agent(db_session, "Streaming E2E Org")

    chunks = [chunk async for chunk in stream_agent_response(db_session, str(agent.id), "Hi", organization_id=org.id)]
    text = "".join(chunks)

    assert "event: start" in text
    assert "event: token" in text
    assert "event: done" in text

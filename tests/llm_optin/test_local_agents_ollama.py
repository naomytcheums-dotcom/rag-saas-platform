"""AI agents and retrieval against a REAL local Ollama server (no mocks at the LLM boundary). Opt-in, free, no key:

    RUN_REAL_LLM_TESTS=1 LOCAL_LLM_BASE_URL=http://127.0.0.1:11434 LOCAL_LLM_MODEL=qwen2.5:7b pytest tests/llm_optin/test_local_agents_ollama.py -q

Covers the agent orchestrator (plain run, answer grounded on retrieved chunks, tenant isolation of that context, the function-calling loop with
the calculator tool), the autonomous agent (LLM planning + execution), and the Ollama embedding endpoint through the shared embedding call site.
A small model may fail to follow a tool-calling instruction: the assertions check what the product did with the model's output, not model quality.
"""

import math
import os
import uuid

import pytest

from api.config import settings
from api.models.autonomous_agent import AutonomousAgent, AutonomousAgentStatus
from api.models.document import Document, DocumentChunk, DocumentStatus
from api.models.organization import Organization
from api.security.documents import generate_embeddings
from api.services import autonomous_agents as autonomous
from api.services.agent_orchestrator import AgentOrchestrator
from api.services.embedding_providers import EmbeddingProviderError, _call_litellm_embedding
from api.services.retrieval_pipeline import build_llm_context, search_with_context
from api.services.tools import CALCULATOR_TOOL

pytestmark = pytest.mark.skipif(os.environ.get("RUN_REAL_LLM_TESTS") != "1", reason="real-LLM tests are opt-in: set RUN_REAL_LLM_TESTS=1")

BASE_URL = os.environ.get("LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434")
MODEL = os.environ.get("LOCAL_LLM_MODEL", "qwen2.5:7b")
EMBED_MODEL = os.environ.get("LOCAL_EMBED_MODEL", "nomic-embed-text")
OVERRIDES = {"provider": "ollama", "model": MODEL}
RETRIEVAL_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


@pytest.fixture(autouse=True)
def local_ollama(monkeypatch):
    monkeypatch.setattr(settings, "OLLAMA_BASE_URL", BASE_URL)
    monkeypatch.setattr(settings, "OLLAMA_MODEL", f"ollama/{MODEL}")
    monkeypatch.setattr(settings, "LLM_DEFAULT_PROVIDER", "ollama")
    monkeypatch.setattr(settings, "LLM_TIMEOUT", 900)
    monkeypatch.setattr(settings, "AGENT_TIMEOUT", 900)
    monkeypatch.setattr(settings, "AGENT_MAX_RETRIES", 0)
    monkeypatch.setattr(settings, "SSE_TIMEOUT", 900.0)


async def _make_org(db_session, name: str) -> Organization:
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


async def _add_document(db_session, org_id, texts: list[str]) -> Document:
    document = Document(
        organization_id=org_id, name="manual.pdf", file_key=f"documents/{uuid.uuid4()}/manual.pdf",
        file_size=100, file_type="application/pdf", status=DocumentStatus.completed.value,
    )
    db_session.add(document)
    await db_session.flush()
    for text, embedding in zip(texts, generate_embeddings(texts, RETRIEVAL_EMBEDDING_MODEL)):
        db_session.add(DocumentChunk(document_id=document.id, organization_id=org_id, content=text, embedding=embedding))
    await db_session.commit()
    return document


async def test_the_orchestrator_runs_an_agent_on_a_real_model(db_session):
    run = await AgentOrchestrator().run_agent("agent-1", "Reply with the single word: pong", db=db_session, llm_overrides=OVERRIDES)

    assert run.status == "completed", run.error
    assert "pong" in run.result.lower()
    assert any(event["event"] == "created" for event in run.trace)


async def test_an_agent_answers_from_retrieved_chunks_and_never_from_another_tenant(db_session):
    org_a = await _make_org(db_session, "Agent Org A")
    org_b = await _make_org(db_session, "Agent Org B")
    await _add_document(db_session, org_a.id, [
        "The Zorblax-9 pump comes with a warranty of 17 months from the date of purchase.",
        "The Zorblax-9 pump must be serviced every 6 months by a certified technician.",
    ])
    await _add_document(db_session, org_b.id, ["The Zorblax-9 pump warranty is 99 months, a confidential term reserved for Org B."])

    question = "How many months does the Zorblax-9 pump warranty last?"
    results = await search_with_context(db_session, org_a.id, question, top_k=3, strategy="vector_only")
    context = build_llm_context(results)

    assert results and "17 months" in context
    assert "99 months" not in context and "Org B" not in context

    run = await AgentOrchestrator().run_agent(
        "agent-1", f"Answer using only the context. {question} Give the number.", db=db_session, context=context, llm_overrides=OVERRIDES,
    )
    assert run.status == "completed", run.error
    assert "17" in run.result
    assert "99" not in run.result


async def test_the_function_calling_loop_executes_the_calculator_tool(db_session):
    run = await AgentOrchestrator().run_agent(
        "agent-1", "Use the calculator tool to compute 1234 * 5678 and tell me the result.", db=db_session,
        tools=[CALCULATOR_TOOL], llm_overrides=OVERRIDES,
    )

    assert run.status == "completed", run.error
    assert any(event["event"] == "tools_selected" and "calculator" in event["tools"] for event in run.trace)
    tool_calls = [event for event in run.trace if event["event"] == "tool_call"]
    assert tool_calls, f"the model never requested the tool; trace events: {[e['event'] for e in run.trace]}"
    assert "7006652" in run.result.replace(",", "").replace(" ", "")


async def test_an_autonomous_agent_plans_and_executes_with_a_real_model(db_session):
    org = await _make_org(db_session, "Autonomous Org")
    agent = AutonomousAgent(organization_id=org.id, name="Planner", goal="Explain in one sentence why the sky is blue.", max_steps=3)
    db_session.add(agent)
    await db_session.commit()

    updated = await autonomous.run_autonomous_agent(db_session, agent.id)
    await db_session.commit()

    plans = await autonomous.list_agent_plans(db_session, agent.id)
    assert plans, "no plan was created"
    steps = await autonomous.list_agent_steps(db_session, plans[0].id)
    assert steps, f"the plan has no step (agent status {updated.status}, error {updated.error})"
    assert updated.status != AutonomousAgentStatus.error.value, updated.error
    assert any(step.status == "completed" and (step.result or {}).get("output") for step in steps)
    assert float(updated.total_cost or 0) >= 0


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b)) / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


async def test_ollama_embeddings_are_real_and_semantically_ordered():
    texts = ["How do I reset my password?", "Steps to change a forgotten account password", "The cheetah is the fastest land animal"]
    vectors = await _call_litellm_embedding(f"ollama/{EMBED_MODEL}", texts, api_base=BASE_URL, timeout=600)

    assert len(vectors) == 3 and len({len(v) for v in vectors}) == 1 and len(vectors[0]) > 100
    assert _cosine(vectors[0], vectors[1]) > _cosine(vectors[0], vectors[2])


async def test_an_unknown_ollama_embedding_model_is_an_embedding_error():
    with pytest.raises(EmbeddingProviderError):
        await _call_litellm_embedding("ollama/no-such-embedding-model", ["hello"], api_base=BASE_URL, timeout=60)


async def test_the_streaming_chat_path_streams_tokens_from_a_real_model(db_session):
    events = [
        event async for event in AgentOrchestrator().stream_response("agent-1", "Reply with the single word: pong", db=db_session, llm_overrides=OVERRIDES)
    ]

    kinds = [event["type"] for event in events]
    assert "error" not in kinds, events
    assert kinds.count("token") >= 1 and kinds[-1] == "done"
    assert "pong" in "".join(event["token"] for event in events if event["type"] == "token").lower()


async def test_the_streaming_chat_path_runs_the_tool_loop_on_a_real_model(db_session, monkeypatch):
    monkeypatch.setattr("api.services.agent_orchestrator.select_tools", lambda query, tools, **kw: _all_tools(tools))
    events = [
        event async for event in AgentOrchestrator().stream_response(
            "agent-1", "Use the calculator tool to compute 1234 * 5678 and tell me the result.", db=db_session, tools=[CALCULATOR_TOOL], llm_overrides=OVERRIDES,
        )
    ]

    kinds = [event["type"] for event in events]
    assert "error" not in kinds, events
    assert "tool_call" in kinds and "tool_result" in kinds and kinds[-1] == "done", "".join(e.get("token", "") for e in events)
    assert any(event["type"] == "tool_result" and event["error"] is None for event in events)


async def _all_tools(tools):
    return tools

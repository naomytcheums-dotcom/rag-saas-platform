"""Hardening Mission (§11, §14, §16, §24) -- regression tests for the real
bugs found in the 4 builtin MCP tools (api/services/mcp/builtin_tools.py)
and their route (api/routers/mcp_server.py):

- cross-tenant: `organization_id` came from the request BODY, never from
  the authenticated key (any `mcp:tools` key could act on any tenant);
- `get_failure_report` / `run_eval_benchmark` never checked ownership
  (IDOR) and the report's question/expected/actual were always empty;
- `retrieval_config` was stored unvalidated, and read by NOTHING at run
  time, so a ChangeLab change could never move a benchmark metric.

Real DB session / real rows throughout; only the LLM and the retrieval
call (a separate, already-tested boundary) are mocked where needed."""

import json
import uuid
from unittest.mock import AsyncMock

import litellm
import pytest
from litellm.types.utils import Choices, Message, ModelResponse

from api.config import settings
from api.models.agent import Agent
from api.models.evaluation import EvaluationDataset, EvaluationFailure, EvaluationJob, EvaluationJobStatus, EvaluationQuestion
from api.models.organization import Organization
from api.services.agent_knowledge_base import (
    AgentKnowledgeBaseError, retrieval_overrides_from_kb_config, validate_retrieval_config,
)
from api.services.mcp import builtin_tools as bt


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _make_org(db_session, name="Org") -> Organization:
    org = Organization(name=name, slug=f"{name.lower()}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


async def _make_job_with_failure(db_session, org: Organization) -> tuple[EvaluationJob, EvaluationQuestion]:
    dataset = EvaluationDataset(organization_id=org.id, name="ds")
    db_session.add(dataset)
    await db_session.flush()
    question = EvaluationQuestion(dataset_id=dataset.id, question="What is the refund window?", expected_answer="30 days")
    db_session.add(question)
    await db_session.flush()
    job = EvaluationJob(dataset_id=dataset.id, status=EvaluationJobStatus.completed)
    db_session.add(job)
    await db_session.flush()
    db_session.add(EvaluationFailure(evaluation_job_id=job.id, question_id=question.id, category="retrieval", error="boom: index unavailable"))
    await db_session.commit()
    return job, question


# ------------------------------------------------------------- pure validation


def test_validate_retrieval_config_normalizes_agents_md_short_strategy_names():
    assert validate_retrieval_config({"strategy": "vector", "top_k": 10})["strategy"] == "vector_only"
    assert validate_retrieval_config({"strategy": "bm25"})["strategy"] == "bm25_only"


def test_validate_retrieval_config_rejects_unknown_keys_and_bad_values():
    for bad in ({"topk": 5}, {"top_k": 0}, {"top_k": settings.TOP_K_MAX + 1}, {"top_k": True}, {"score_threshold": 1.5}, {"strategy": "made_up"}, {"hyde": "yes"}):
        with pytest.raises(AgentKnowledgeBaseError):
            validate_retrieval_config(bad)


def test_retrieval_overrides_from_kb_config_splits_search_kwargs_from_setting_flags():
    kwargs, overrides = retrieval_overrides_from_kb_config({"top_k": 10, "strategy": "vector", "reranker": "none", "hyde": True, "junk": 1})
    assert kwargs == {"top_k": 10, "strategy": "vector_only"}
    assert overrides == {"hyde_enabled": True}


def test_retrieval_overrides_from_kb_config_skips_malformed_legacy_values_instead_of_breaking_a_query():
    assert retrieval_overrides_from_kb_config({"top_k": "ten", "score_threshold": 9, "strategy": "nope"}) == ({}, {})
    assert retrieval_overrides_from_kb_config(None) == ({}, {})


# ------------------------------------------------------------------ the tools


async def test_create_rag_agent_rejects_an_invalid_retrieval_config(db_session):
    org = await _make_org(db_session)
    result = await bt.call_builtin_tool(db_session, "create_rag_agent", {"organization_id": str(org.id), "name": "A", "retrieval_config": {"topk": 5}})
    assert result["is_error"] is True
    assert "Unknown retrieval_config key" in result["content"][0]["text"]


async def test_create_rag_agent_stores_the_validated_normalized_config(db_session):
    org = await _make_org(db_session)
    result = await bt.call_builtin_tool(db_session, "create_rag_agent", {"organization_id": str(org.id), "name": "A", "retrieval_config": {"strategy": "vector", "top_k": 10}})
    assert result["is_error"] is False
    agent = await db_session.get(Agent, uuid.UUID(json.loads(result["content"][0]["text"])["agent_id"]))
    assert agent.knowledge_base_config == {"strategy": "vector_only", "top_k": 10}


async def test_update_retrieval_config_merges_and_rejects_typos(db_session):
    org = await _make_org(db_session)
    created = await bt.call_builtin_tool(db_session, "create_rag_agent", {"organization_id": str(org.id), "name": "A", "retrieval_config": {"top_k": 5}})
    agent_id = json.loads(created["content"][0]["text"])["agent_id"]

    ok = await bt.call_builtin_tool(db_session, "update_retrieval_config", {"organization_id": str(org.id), "agent_id": agent_id, "config": {"top_k": 10}})
    bad = await bt.call_builtin_tool(db_session, "update_retrieval_config", {"organization_id": str(org.id), "agent_id": agent_id, "config": {"topk": 10}})

    assert ok["is_error"] is False
    assert bad["is_error"] is True
    assert (await db_session.get(Agent, uuid.UUID(agent_id))).knowledge_base_config == {"top_k": 10}


async def test_get_failure_report_returns_the_real_question_expected_and_error(db_session):
    org = await _make_org(db_session)
    job, _question = await _make_job_with_failure(db_session, org)

    result = await bt.call_builtin_tool(db_session, "get_failure_report", {"organization_id": str(org.id), "run_id": str(job.id)})

    assert result["is_error"] is False
    report = json.loads(result["content"][0]["text"])
    assert report["failures"] == [{"question": "What is the refund window?", "category": "retrieval", "expected": "30 days", "actual": "boom: index unavailable"}]
    assert report["categories"]["retrieval"] == 1


async def test_get_failure_report_never_leaks_another_organizations_run(db_session):
    """IDOR regression: organization B asking for organization A's run
    gets exactly the same answer as for a run that does not exist."""
    org_a = await _make_org(db_session, "OrgA")
    org_b = await _make_org(db_session, "OrgB")
    job_a, _ = await _make_job_with_failure(db_session, org_a)

    cross = await bt.call_builtin_tool(db_session, "get_failure_report", {"organization_id": str(org_b.id), "run_id": str(job_a.id)})
    missing = await bt.call_builtin_tool(db_session, "get_failure_report", {"organization_id": str(org_b.id), "run_id": str(uuid.uuid4())})

    assert cross["is_error"] is True and missing["is_error"] is True
    assert "boom" not in cross["content"][0]["text"]
    assert cross["content"][0]["text"].startswith("Run not found")


async def test_run_eval_benchmark_refuses_another_organizations_dataset_and_agent(db_session):
    org_a = await _make_org(db_session, "OrgA")
    org_b = await _make_org(db_session, "OrgB")
    job_a, _ = await _make_job_with_failure(db_session, org_a)
    dataset_a = (await db_session.get(EvaluationJob, job_a.id)).dataset_id
    foreign_agent = Agent(organization_id=org_a.id, name="a", system_prompt="x", model_config_json={})
    db_session.add(foreign_agent)
    await db_session.commit()

    cross_dataset = await bt.call_builtin_tool(db_session, "run_eval_benchmark", {"organization_id": str(org_b.id), "dataset_id": str(dataset_a)})
    own_dataset_b = EvaluationDataset(organization_id=org_b.id, name="b")
    db_session.add(own_dataset_b)
    await db_session.commit()
    cross_agent = await bt.call_builtin_tool(
        db_session, "run_eval_benchmark", {"organization_id": str(org_b.id), "dataset_id": str(own_dataset_b.id), "agent_id": str(foreign_agent.id)},
    )

    assert cross_dataset["is_error"] is True and "Dataset not found" in cross_dataset["content"][0]["text"]
    assert cross_agent["is_error"] is True and "Agent not found" in cross_agent["content"][0]["text"]


# ------------------------------------------------- the route binds org to the key


async def _register_org_and_key(client, email: str, password: str, org_name: str):
    token = (await client.post("/auth/register", json={"email": email, "password": password, "accept_terms": True})).json()["access_token"]
    org_id = (await client.post("/organizations", json={"name": org_name}, headers=_auth_header(token))).json()["id"]
    key = (await client.post(f"/organizations/{org_id}/api-keys", json={"name": "k", "scopes": ["mcp:tools"]}, headers=_auth_header(token))).json()["key"]
    return org_id, key


async def test_mcp_route_rejects_a_body_organization_id_that_is_not_the_keys_own(client, db_session, register_payload):
    _org_a, key_a = await _register_org_and_key(client, register_payload["email"], register_payload["password"], "OrgA")
    org_b = await _make_org(db_session, "OrgB")
    await db_session.commit()

    response = await client.post(
        "/mcp/v1/tools/create_rag_agent/call", json={"organization_id": str(org_b.id), "name": "Intruder"}, headers={"X-API-Key": key_a},
    )

    assert response.status_code == 403
    from sqlalchemy import select

    assert await db_session.scalar(select(Agent).where(Agent.organization_id == org_b.id)) is None


async def test_mcp_route_fills_in_the_keys_own_organization_when_omitted(client, db_session, register_payload):
    org_a, key_a = await _register_org_and_key(client, register_payload["email"], register_payload["password"], "OrgA")

    response = await client.post("/mcp/v1/tools/create_rag_agent/call", json={"name": "Mine"}, headers={"X-API-Key": key_a})

    assert response.status_code == 200
    body = response.json()
    assert body["is_error"] is False
    agent = await db_session.get(Agent, uuid.UUID(json.loads(body["content"][0]["text"])["agent_id"]))
    assert str(agent.organization_id) == org_a


async def test_mcp_route_rate_limits_builtin_tools_and_shares_the_evaluation_budget(monkeypatch, client, register_payload):
    from fastapi import HTTPException, status

    org_a, key_a = await _register_org_and_key(client, register_payload["email"], register_payload["password"], "OrgA")
    seen = []

    async def _fake_enforce(key, max_attempts, window_seconds):
        seen.append(key)
        if key.startswith("ratelimit:evaluation_run"):
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts", headers={"Retry-After": "60"})

    monkeypatch.setattr("api.routers.mcp_server.enforce_rate_limit", _fake_enforce)
    response = await client.post("/mcp/v1/tools/run_eval_benchmark/call", json={"dataset_id": str(uuid.uuid4())}, headers={"X-API-Key": key_a})

    assert response.status_code == 429
    assert f"ratelimit:mcp_builtin:org:{org_a}" in seen
    assert f"ratelimit:evaluation_run:org:{org_a}" in seen


# --------------------------------- ChangeLab is measurable: the Eval Lab applies it


def _fake_llm_response(text: str) -> ModelResponse:
    return ModelResponse(choices=[Choices(message=Message(content=text, role="assistant"), index=0, finish_reason="stop")])


async def _run_evaluation_capturing_search_kwargs(monkeypatch, db_session, *, agent_org_is_same: bool, kb_config: dict, retrieval_overrides: dict | None = None):
    from api.services.evaluation_results import run_evaluation

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_fake_llm_response("An answer.")))
    search_mock = AsyncMock(return_value=[])
    monkeypatch.setattr("api.services.evaluation_results.search_with_context", search_mock)

    org = await _make_org(db_session, "Eval")
    other = await _make_org(db_session, "Other")
    dataset = EvaluationDataset(organization_id=org.id, name="ds")
    db_session.add(dataset)
    await db_session.flush()
    question = EvaluationQuestion(dataset_id=dataset.id, question="Q?", expected_answer="A")
    agent = Agent(organization_id=(org if agent_org_is_same else other).id, name="agent", system_prompt="x", model_config_json={}, knowledge_base_config=kb_config)
    db_session.add_all([question, agent])
    await db_session.commit()

    await run_evaluation(db_session, question.id, agent_id=agent.id, retrieval_overrides=retrieval_overrides)
    return search_mock.await_args


async def test_eval_lab_applies_the_agents_stored_retrieval_config(monkeypatch, db_session):
    call = await _run_evaluation_capturing_search_kwargs(
        monkeypatch, db_session, agent_org_is_same=True, kb_config={"top_k": 10, "strategy": "vector_only", "hyde": True},
    )
    assert call.kwargs["top_k"] == 10
    assert call.kwargs["strategy"] == "vector_only"
    assert call.kwargs["org_settings"]["hyde_enabled"] is True


async def test_explicit_retrieval_overrides_still_beat_the_agents_stored_config(monkeypatch, db_session):
    call = await _run_evaluation_capturing_search_kwargs(
        monkeypatch, db_session, agent_org_is_same=True, kb_config={"top_k": 10}, retrieval_overrides={"top_k": 3},
    )
    assert call.kwargs["top_k"] == 3


async def test_eval_lab_never_applies_another_organizations_agent_config(monkeypatch, db_session):
    call = await _run_evaluation_capturing_search_kwargs(monkeypatch, db_session, agent_org_is_same=False, kb_config={"top_k": 10})
    assert "top_k" not in call.kwargs

"""Hardening Mission, §14 -- Factory: requirement -> blueprint -> validation
-> real agent -> optional measured gate. The blueprint rules are tested
purely; deployment runs against a real DB session and the REAL
`create_agent`; the benchmark itself is mocked at its own tested boundary."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from api.models.agent import Agent
from api.models.evaluation import EvaluationDataset
from api.models.organization import Organization
from api.services.agent_factory import FactoryError, build_agent_blueprint, deploy_blueprint, validate_blueprint
from api.services.agent_knowledge_base import validate_retrieval_config


# ------------------------------------------------------------------ blueprint (pure)


def test_a_compliance_requirement_gets_the_precision_profile():
    blueprint = build_agent_blueprint("Answer questions about our legal contracts and compliance policies")
    assert blueprint["profile"] == "compliance"
    assert blueprint["retrieval_config"]["strategy"] == "hybrid_reranked"
    agent = blueprint["agent"]
    assert agent["citation_required"] is True and agent["answer_only_from_context"] is True and agent["idk_threshold"] == 0.3


def test_french_requirements_are_understood_too():
    assert build_agent_blueprint("Répondre aux questions juridiques sur nos contrats clients")["profile"] == "compliance"
    assert build_agent_blueprint("Un assistant de support pour le service client")["profile"] == "support"


def test_profiles_differ_in_the_retrieval_they_configure():
    research = build_agent_blueprint("Research and summarize market reports for the strategy team")
    support = build_agent_blueprint("Customer support FAQ assistant for our helpdesk")
    assert research["retrieval_config"]["mmr"] is True and research["retrieval_config"]["top_k"] == 12
    assert support["retrieval_config"] == {"strategy": "hybrid", "top_k": 5}


def test_every_blueprint_searches_the_knowledge_base_and_detects_prompt_injection():
    for requirement in ("Help our engineers with the API documentation", "A general assistant for the company handbook"):
        blueprint = build_agent_blueprint(requirement)
        assert {"name": "search_knowledge_base", "enabled": True, "config": {}} in blueprint["agent"]["tools"]
        assert blueprint["agent"]["prompt_injection_detection_enabled"] is True


def test_extra_tools_are_added_only_when_the_requirement_asks_for_the_capability():
    plain = build_agent_blueprint("Answer HR questions from the employee handbook")
    rich = build_agent_blueprint("Answer HR questions, search the web for recent news and escalate to a human when unsure")
    plain_tools = {t["name"] for t in plain["agent"]["tools"]}
    rich_tools = {t["name"] for t in rich["agent"]["tools"]}
    assert plain_tools == {"search_knowledge_base"}
    assert {"web_search", "escalate_to_human"} <= rich_tools


def test_the_tool_list_is_restricted_to_the_real_catalog_when_one_is_pinned():
    blueprint = build_agent_blueprint("Answer questions and search the web for news", registered_tools={"search_knowledge_base"})
    assert {t["name"] for t in blueprint["agent"]["tools"]} == {"search_knowledge_base"}


def test_a_blueprint_is_deterministic_and_carries_its_rationale():
    first = build_agent_blueprint("Customer support FAQ assistant")
    second = build_agent_blueprint("Customer support FAQ assistant")
    assert first == second
    assert first["rationale"][0].startswith("profile 'support'")


def test_a_vague_or_empty_requirement_is_refused():
    for bad in ("", "   ", "help"):
        with pytest.raises(FactoryError):
            build_agent_blueprint(bad)


def test_every_default_profile_blueprint_passes_the_platforms_own_validators():
    requirements = (
        "legal contract review", "customer support FAQ", "API developer documentation", "research and summarize reports", "company handbook assistant",
    )
    for requirement in requirements:
        blueprint = build_agent_blueprint(f"An assistant for: {requirement}")
        assert validate_blueprint(blueprint) == [], requirement
        validate_retrieval_config(blueprint["retrieval_config"])  # the Eval Lab / ChangeLab vocabulary


def test_validate_blueprint_lists_every_problem_at_once():
    blueprint = build_agent_blueprint("Customer support assistant for our helpdesk")
    blueprint["retrieval_config"] = {"topk": 3}
    blueprint["agent"]["tools"] = [{"name": "does_not_exist"}]
    blueprint["agent"]["idk_threshold"] = 7
    blueprint["agent"]["memory_window_size"] = -1

    problems = validate_blueprint(blueprint)

    assert len(problems) >= 4
    assert any(p.startswith("retrieval_config") for p in problems)
    assert any(p.startswith("tools") for p in problems)
    assert any(p.startswith("idk_threshold") for p in problems)
    assert any(p.startswith("memory") for p in problems)


# ----------------------------------------------------------------- deployment (DB)


async def _org(db_session) -> Organization:
    org = Organization(name="Factory Org", slug=f"factory-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.commit()
    return org


async def test_deploy_creates_a_real_agent_carrying_the_blueprints_configuration(db_session):
    org = await _org(db_session)
    blueprint = build_agent_blueprint("Answer questions about our legal contracts and compliance policies", name="Contract Bot")

    result = await deploy_blueprint(db_session, org.id, blueprint, created_by=None)
    await db_session.commit()

    assert result["decision"] == "deployed" and result["status"] == "active" and result["metrics"] is None
    agent = await db_session.scalar(select(Agent).where(Agent.id == result["agent_id"]))
    assert agent.organization_id == org.id and agent.name == "Contract Bot"
    assert agent.citation_required is True and agent.answer_only_from_context is True and agent.prompt_injection_detection_enabled is True
    assert agent.knowledge_base_config == blueprint["retrieval_config"]
    assert [t["name"] for t in agent.tools] == ["search_knowledge_base"]


async def test_deploy_refuses_an_invalid_blueprint_and_writes_nothing(db_session):
    org = await _org(db_session)
    blueprint = build_agent_blueprint("Customer support assistant for our helpdesk")
    blueprint["agent"]["tools"] = [{"name": "does_not_exist"}]

    with pytest.raises(FactoryError):
        await deploy_blueprint(db_session, org.id, blueprint, created_by=None)

    assert await db_session.scalar(select(Agent).where(Agent.organization_id == org.id)) is None


async def test_deploy_refuses_another_organizations_dataset(db_session):
    org, other = await _org(db_session), await _org(db_session)
    dataset = EvaluationDataset(organization_id=other.id, name="theirs")
    db_session.add(dataset)
    await db_session.commit()

    with pytest.raises(FactoryError, match="dataset not found"):
        await deploy_blueprint(db_session, org.id, build_agent_blueprint("Customer support assistant"), None, evaluate_dataset_id=dataset.id)
    assert await db_session.scalar(select(Agent).where(Agent.organization_id == org.id)) is None


async def _deploy_with_measured_recall(db_session, measured: float | None, minimum: float | None):
    org = await _org(db_session)
    dataset = EvaluationDataset(organization_id=org.id, name="gate")
    db_session.add(dataset)
    await db_session.commit()
    job = MagicMock()
    job.id = uuid.uuid4()
    metrics = {} if measured is None else {"recall_at_5": measured}
    with patch("api.services.evaluation_jobs.create_evaluation_job", AsyncMock(return_value=job)) as create, \
         patch("api.services.evaluation_jobs.run_evaluation_job", AsyncMock(return_value=job)), \
         patch("api.services.mcp.builtin_tools._job_metric_averages", AsyncMock(return_value=metrics)):
        result = await deploy_blueprint(
            db_session, org.id, build_agent_blueprint("Customer support assistant"), None, evaluate_dataset_id=dataset.id, min_target_value=minimum,
        )
    return result, create


async def test_an_agent_that_meets_its_measured_bar_is_deployed_active(db_session):
    result, create = await _deploy_with_measured_recall(db_session, measured=0.9, minimum=0.8)
    assert result["decision"] == "deployed_and_evaluated" and result["status"] == "active" and result["metrics"] == {"recall_at_5": 0.9}
    assert create.await_args.kwargs["agent_id"] == result["agent_id"]  # the AGENT is what gets benchmarked


async def test_an_agent_below_its_bar_is_created_but_held_back_paused(db_session):
    result, _ = await _deploy_with_measured_recall(db_session, measured=0.5, minimum=0.8)
    assert result["decision"] == "held_back" and result["status"] == "paused"


async def test_an_unmeasurable_target_metric_is_held_back_not_waved_through(db_session):
    result, _ = await _deploy_with_measured_recall(db_session, measured=None, minimum=0.8)
    assert result["decision"] == "held_back" and result["status"] == "paused"


async def test_without_a_minimum_the_evaluation_is_informational_and_the_agent_stays_active(db_session):
    result, _ = await _deploy_with_measured_recall(db_session, measured=0.1, minimum=None)
    assert result["decision"] == "deployed_and_evaluated" and result["status"] == "active"


# ------------------------------------------------------------------- the routes


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _owner_with_org(client, register_payload):
    token = (await client.post("/auth/register", json={"email": register_payload["email"], "password": register_payload["password"], "accept_terms": True})).json()["access_token"]
    org_id = (await client.post("/organizations", json={"name": "Route Org"}, headers=_auth_header(token))).json()["id"]
    return token, org_id


async def test_the_blueprint_route_is_a_dry_run_that_writes_nothing(client, db_session, register_payload):
    token, org_id = await _owner_with_org(client, register_payload)

    response = await client.post(f"/organizations/{org_id}/factory/blueprint", json={"requirement": "Customer support FAQ assistant for our helpdesk"}, headers=_auth_header(token))

    assert response.status_code == 200
    body = response.json()
    assert body["deployable"] is True and body["problems"] == [] and body["blueprint"]["profile"] == "support"
    assert await db_session.scalar(select(Agent).where(Agent.organization_id == uuid.UUID(org_id))) is None


async def test_the_deploy_route_creates_the_agent_and_rejects_a_vague_requirement(client, db_session, register_payload):
    token, org_id = await _owner_with_org(client, register_payload)

    ok = await client.post(f"/organizations/{org_id}/factory/deploy", json={"requirement": "Customer support FAQ assistant for our helpdesk", "name": "Helpdesk"}, headers=_auth_header(token))
    vague = await client.post(f"/organizations/{org_id}/factory/deploy", json={"requirement": "help"}, headers=_auth_header(token))

    assert ok.status_code == 201 and ok.json()["decision"] == "deployed"
    agent = await db_session.scalar(select(Agent).where(Agent.id == uuid.UUID(ok.json()["agent_id"])))
    assert agent.name == "Helpdesk" and str(agent.organization_id) == org_id
    assert vague.status_code == 422


async def test_the_deploy_route_refuses_a_zero_balance_before_evaluating(monkeypatch, client, db_session, register_payload):
    from api.models.billing import Credit

    token, org_id = await _owner_with_org(client, register_payload)
    dataset = EvaluationDataset(organization_id=uuid.UUID(org_id), name="mine")
    db_session.add(dataset)
    credit = await db_session.scalar(select(Credit).where(Credit.organization_id == uuid.UUID(org_id)))
    if credit is None:
        db_session.add(Credit(organization_id=uuid.UUID(org_id), balance=0))
    else:
        credit.balance = 0
    await db_session.commit()
    create = AsyncMock()
    monkeypatch.setattr("api.services.evaluation_jobs.create_evaluation_job", create)

    response = await client.post(
        f"/organizations/{org_id}/factory/deploy", json={"requirement": "Customer support FAQ assistant", "evaluate_dataset_id": str(dataset.id)}, headers=_auth_header(token),
    )

    assert response.status_code == 402
    create.assert_not_awaited()
    assert await db_session.scalar(select(Agent).where(Agent.organization_id == uuid.UUID(org_id))) is None


async def test_the_factory_routes_need_the_agents_write_permission(client, db_session, register_payload):
    from api.models.organization import OrganizationMember, OrganizationRole
    from api.models.user import User

    _owner_token, org_id = await _owner_with_org(client, register_payload)
    email = f"viewer-{uuid.uuid4().hex[:8]}@example.com"
    viewer_token = (await client.post("/auth/register", json={"email": email, "password": "correct-horse-battery-staple", "accept_terms": True})).json()["access_token"]
    viewer = await db_session.scalar(select(User).where(User.email == email))
    db_session.add(OrganizationMember(organization_id=uuid.UUID(org_id), user_id=viewer.id, role=OrganizationRole.viewer))
    await db_session.commit()

    response = await client.post(f"/organizations/{org_id}/factory/deploy", json={"requirement": "Customer support FAQ assistant"}, headers=_auth_header(viewer_token))

    assert response.status_code == 403

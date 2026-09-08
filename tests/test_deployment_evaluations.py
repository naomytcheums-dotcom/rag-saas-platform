"""Partie 7.3.8 -- auto-eval before deployment. Fast SQLite suite;
litellm/search_with_context mocked at the same boundary as
tests/test_evaluation_results.py."""

import uuid
from unittest.mock import AsyncMock

import litellm
from litellm.types.utils import Choices, Message, ModelResponse

from api.config import settings
from api.models.agent import Agent
from api.models.evaluation import DeploymentEvaluationStatus, EvaluationDataset, EvaluationQuestion
from api.models.organization import Organization
from api.services.deployment_evaluations import (
    check_deployment_thresholds, create_deployment_evaluation, deploy_agent, list_deployment_evaluations,
    pass_deployment_evaluation, run_deployment_evaluation,
)


def _real_response(text: str) -> ModelResponse:
    message = Message(content=text, role="assistant")
    choice = Choices(message=message, index=0, finish_reason="stop")
    return ModelResponse(choices=[choice])


async def _make_org(db_session, name):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


async def _make_agent_and_dataset(db_session, org_id, question_count=1):
    agent = Agent(organization_id=org_id, name="Bot", system_prompt="You are helpful.")
    db_session.add(agent)
    dataset = EvaluationDataset(organization_id=org_id, name="D")
    db_session.add(dataset)
    await db_session.flush()
    for i in range(question_count):
        db_session.add(EvaluationQuestion(dataset_id=dataset.id, question=f"Question {i}?"))
    await db_session.commit()
    return agent, dataset


async def test_create_deployment_evaluation_defaults_the_real_thresholds(db_session):
    """Validation criterion: la création d'évaluation fonctionne."""
    org = await _make_org(db_session, "Deploy Eval Org")
    await db_session.commit()
    agent, dataset = await _make_agent_and_dataset(db_session, org.id)

    evaluation = await create_deployment_evaluation(db_session, agent.id, dataset.id, "v1.0.0")
    await db_session.commit()

    assert evaluation.status == DeploymentEvaluationStatus.pending
    assert "faithfulness" in evaluation.thresholds


async def test_run_deployment_evaluation_passes_when_real_thresholds_are_met(monkeypatch, db_session):
    """Validation criterion: l'exécution fonctionne, la validation des seuils fonctionne."""
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr("api.services.evaluation_results.search_with_context", AsyncMock(return_value=[]))
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("An answer.")))

    org = await _make_org(db_session, "Deploy Eval Pass Org")
    await db_session.commit()
    agent, dataset = await _make_agent_and_dataset(db_session, org.id)
    # Real, deliberately trivial thresholds -- any real, non-empty answer clears them.
    evaluation = await create_deployment_evaluation(db_session, agent.id, dataset.id, "v1.0.0", thresholds={"faithfulness": 0.0})
    await db_session.commit()

    updated = await run_deployment_evaluation(db_session, evaluation.id)

    assert updated.status == DeploymentEvaluationStatus.passed
    assert updated.evaluation_job_id is not None
    assert updated.results["violations"] == []


async def test_run_deployment_evaluation_fails_when_a_real_threshold_is_violated(monkeypatch, db_session):
    """Validation criterion: robustesse -- une métrique échoue."""
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr("api.services.evaluation_results.search_with_context", AsyncMock(return_value=[]))
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("An answer.")))

    org = await _make_org(db_session, "Deploy Eval Fail Org")
    await db_session.commit()
    agent, dataset = await _make_agent_and_dataset(db_session, org.id)
    evaluation = await create_deployment_evaluation(db_session, agent.id, dataset.id, "v1.0.0", thresholds={"faithfulness": 1.1})
    await db_session.commit()

    updated = await run_deployment_evaluation(db_session, evaluation.id)

    assert updated.status == DeploymentEvaluationStatus.failed
    assert len(updated.results["violations"]) == 1


async def test_run_deployment_evaluation_is_honestly_none_for_an_unknown_evaluation(db_session):
    """Validation criterion: robustesse."""
    assert await run_deployment_evaluation(db_session, uuid.uuid4()) is None


async def test_pass_deployment_evaluation_overrides_a_real_failure(monkeypatch, db_session):
    """Validation criterion: la validation des seuils fonctionne (override manuel)."""
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr("api.services.evaluation_results.search_with_context", AsyncMock(return_value=[]))
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("An answer.")))

    org = await _make_org(db_session, "Deploy Eval Override Org")
    await db_session.commit()
    agent, dataset = await _make_agent_and_dataset(db_session, org.id)
    evaluation = await create_deployment_evaluation(db_session, agent.id, dataset.id, "v1.0.0", thresholds={"faithfulness": 1.1})
    await db_session.commit()
    await run_deployment_evaluation(db_session, evaluation.id)

    overridden = await pass_deployment_evaluation(db_session, evaluation.id)
    await db_session.commit()
    assert overridden.status == DeploymentEvaluationStatus.passed


async def test_deploy_agent_is_honestly_blocked_with_no_real_evaluation(db_session):
    """Validation criterion: robustesse."""
    org = await _make_org(db_session, "Deploy Agent No Eval Org")
    await db_session.commit()
    agent, _dataset = await _make_agent_and_dataset(db_session, org.id)

    result = await deploy_agent(db_session, agent.id)
    assert result["deployed"] is False


async def test_deploy_agent_succeeds_after_a_real_passed_evaluation(monkeypatch, db_session):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr("api.services.evaluation_results.search_with_context", AsyncMock(return_value=[]))
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("An answer.")))

    org = await _make_org(db_session, "Deploy Agent Org")
    await db_session.commit()
    agent, dataset = await _make_agent_and_dataset(db_session, org.id)
    evaluation = await create_deployment_evaluation(db_session, agent.id, dataset.id, "v1.0.0", thresholds={"faithfulness": 0.0})
    await db_session.commit()
    await run_deployment_evaluation(db_session, evaluation.id)

    result = await deploy_agent(db_session, agent.id)
    assert result["deployed"] is True


async def test_check_deployment_thresholds_is_honestly_none_without_real_results(db_session):
    """Validation criterion: robustesse."""
    org = await _make_org(db_session, "Deploy Eval Check Org")
    await db_session.commit()
    agent, dataset = await _make_agent_and_dataset(db_session, org.id)
    evaluation = await create_deployment_evaluation(db_session, agent.id, dataset.id, "v1.0.0")
    await db_session.commit()

    assert await check_deployment_thresholds(db_session, evaluation.id) is None


async def test_list_deployment_evaluations_paginates(db_session):
    org = await _make_org(db_session, "Deploy Eval List Org")
    await db_session.commit()
    agent, dataset = await _make_agent_and_dataset(db_session, org.id, question_count=0)
    for i in range(3):
        await create_deployment_evaluation(db_session, agent.id, dataset.id, f"v{i}")
    await db_session.commit()

    page = await list_deployment_evaluations(db_session, agent.id, limit=2, offset=0)
    assert page["total"] == 3
    assert len(page["items"]) == 2

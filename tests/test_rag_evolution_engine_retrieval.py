"""Hardening Mission, §12 (Evolution Engine) -- the retrieval-configuration
search: several candidates per cycle, a minimum-improvement threshold, a
no-regression guard across metrics, an explicit apply step with rollback.
Decision logic is tested purely; the job layer is mocked at its own
already-tested boundary (like tests/test_rag_evolution_engine.py), and one
test drives the REAL job path to prove a candidate's config genuinely
reaches the retrieval call."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import litellm
import pytest
from litellm.types.utils import Choices, Message, ModelResponse

from api.config import settings
from api.models.agent import Agent
from api.models.evaluation import EvaluationDataset, EvaluationQuestion
from api.models.organization import Organization
from api.services.agent_knowledge_base import AgentKnowledgeBaseError
from api.services.rag_evolution_engine import (
    apply_retrieval_recommendation, default_retrieval_candidates, judge_candidate, run_retrieval_evolution_cycle,
)


def _comparison(**deltas) -> dict:
    return {"diff": [{"metric": m, "a": 0.5, "b": 0.5 + d, "delta": d} for m, d in deltas.items()]}


# ------------------------------------------------------------- judge_candidate (pure)


def test_a_candidate_with_a_real_gain_and_no_regression_is_accepted():
    verdict = judge_candidate(_comparison(recall_at_5=0.10, mrr=0.01, hallucination_rate=0.0), "recall_at_5", 0.02, 0.05)
    assert verdict == {"accepted": True, "target_delta": pytest.approx(0.10), "reasons": []}


def test_a_gain_below_the_minimum_improvement_is_noise_not_a_win():
    verdict = judge_candidate(_comparison(recall_at_5=0.005), "recall_at_5", 0.02, 0.05)
    assert verdict["accepted"] is False and "below the required minimum" in verdict["reasons"][0]


def test_a_candidate_that_improves_the_target_by_degrading_another_metric_is_rejected_with_the_reason():
    verdict = judge_candidate(_comparison(recall_at_5=0.20, mrr=-0.12), "recall_at_5", 0.02, 0.05)
    assert verdict["accepted"] is False
    assert any("mrr regressed by -0.1200" in r for r in verdict["reasons"])


def test_hallucination_rate_regression_is_direction_aware_an_increase_is_the_bad_direction():
    worse = judge_candidate(_comparison(recall_at_5=0.10, hallucination_rate=+0.10), "recall_at_5", 0.02, 0.05)
    better = judge_candidate(_comparison(recall_at_5=0.10, hallucination_rate=-0.10), "recall_at_5", 0.02, 0.05)
    assert worse["accepted"] is False and any("hallucination_rate" in r for r in worse["reasons"])
    assert better["accepted"] is True


def test_any_ndcg_metric_is_a_guard_whatever_its_k():
    verdict = judge_candidate(_comparison(recall_at_5=0.10, ndcg_at_5=-0.20), "recall_at_5", 0.02, 0.05)
    assert verdict["accepted"] is False and any("ndcg_at_5" in r for r in verdict["reasons"])


def test_a_missing_target_metric_is_reported_not_guessed():
    verdict = judge_candidate(_comparison(mrr=0.1), "recall_at_5", 0.02, 0.05)
    assert verdict["accepted"] is False and verdict["target_delta"] is None and "was not computed" in verdict["reasons"][0]


# ------------------------------------------------------------ candidate generation


def test_default_candidates_are_valid_distinct_and_really_differ_from_the_baseline():
    candidates = default_retrieval_candidates({"top_k": 5})
    assert {"top_k": 10} in candidates and {"strategy": "hybrid_reranked"} in candidates and {"mmr": True} in candidates
    assert len({tuple(sorted(c.items())) for c in candidates}) == len(candidates)


def test_default_candidates_never_exceed_the_top_k_ceiling():
    candidates = default_retrieval_candidates({"top_k": settings.TOP_K_MAX})
    assert all(c.get("top_k", 1) <= settings.TOP_K_MAX for c in candidates)
    assert {"top_k": settings.TOP_K_MAX} not in candidates  # identical to the baseline


# ----------------------------------------------------------------- the cycle


async def _make_dataset(db_session) -> EvaluationDataset:
    org = Organization(name="Evo Org", slug=f"evo-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    dataset = EvaluationDataset(organization_id=org.id, name="ds")
    db_session.add(dataset)
    await db_session.commit()
    return dataset


def _job(job_id, results=None):
    job = MagicMock()
    job.id = job_id
    job.results = results or {"corpus_constrained": False}
    return job


async def test_the_cycle_tests_every_candidate_and_recommends_only_the_best_accepted_one(db_session):
    dataset = await _make_dataset(db_session)
    baseline, c1, c2, c3 = (uuid.uuid4() for _ in range(4))
    comparisons = [
        _comparison(recall_at_5=0.05, mrr=0.0),                 # accepted, small gain
        _comparison(recall_at_5=0.30, mrr=-0.20),               # big gain but regresses mrr -> rejected
        _comparison(recall_at_5=0.12, mrr=0.02),                # accepted, best
    ]
    candidates = [{"top_k": 10}, {"strategy": "hybrid_reranked"}, {"mmr": True}]

    with patch("api.services.evaluation_jobs.create_evaluation_job", AsyncMock(side_effect=[_job(baseline), _job(c1), _job(c2), _job(c3)])) as create, \
         patch("api.services.evaluation_jobs.run_evaluation_job", AsyncMock(side_effect=[_job(baseline), _job(c1), _job(c2), _job(c3)])), \
         patch("api.services.evaluation_jobs.compare_evaluation_jobs", AsyncMock(side_effect=comparisons)):
        result = await run_retrieval_evolution_cycle(db_session, dataset.id, candidates)

    assert result["decision"] == "candidate_recommended"
    assert result["recommended_config"] == {"mmr": True}
    assert [c["accepted"] for c in result["candidates"]] == [True, False, True]
    assert any("mrr regressed" in r for r in result["candidates"][1]["reasons"])
    # every candidate really was a separate job carrying its own retrieval_config
    configs_sent = [call.kwargs.get("model_config") for call in create.await_args_list[1:]]
    assert configs_sent == [{"retrieval_config": c} for c in candidates]
    assert result["corpus_constrained"] is False


async def test_the_cycle_keeps_the_baseline_when_no_candidate_clears_the_bar(db_session):
    dataset = await _make_dataset(db_session)
    ids = [uuid.uuid4(), uuid.uuid4()]
    with patch("api.services.evaluation_jobs.create_evaluation_job", AsyncMock(side_effect=[_job(i) for i in ids])), \
         patch("api.services.evaluation_jobs.run_evaluation_job", AsyncMock(side_effect=[_job(i) for i in ids])), \
         patch("api.services.evaluation_jobs.compare_evaluation_jobs", AsyncMock(return_value=_comparison(recall_at_5=0.001))):
        result = await run_retrieval_evolution_cycle(db_session, dataset.id, [{"top_k": 10}])

    assert result["decision"] == "baseline_kept" and result["recommended_config"] is None


async def test_the_cycle_rejects_an_invalid_candidate_before_spending_anything(db_session):
    dataset = await _make_dataset(db_session)
    with patch("api.services.evaluation_jobs.create_evaluation_job", AsyncMock()) as create:
        with pytest.raises(AgentKnowledgeBaseError):
            await run_retrieval_evolution_cycle(db_session, dataset.id, [{"topk": 10}])
    create.assert_not_awaited()


async def test_the_cycle_refuses_an_unknown_dataset(db_session):
    with pytest.raises(ValueError, match="Dataset not found"):
        await run_retrieval_evolution_cycle(db_session, uuid.uuid4(), [{"top_k": 10}])


async def test_a_candidates_retrieval_config_really_reaches_the_retrieval_call_through_the_real_job_path(monkeypatch, db_session):
    """No mocking of the job layer: a job created with
    `model_config={"retrieval_config": ...}` makes `run_evaluation` call
    `search_with_context` with exactly that configuration."""
    from api.services.evaluation_jobs import create_evaluation_job, run_evaluation_job

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    response = ModelResponse(choices=[Choices(message=Message(content="An answer.", role="assistant"), index=0, finish_reason="stop")])
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=response))
    search_mock = AsyncMock(return_value=[])
    monkeypatch.setattr("api.services.evaluation_results.search_with_context", search_mock)

    dataset = await _make_dataset(db_session)
    db_session.add(EvaluationQuestion(dataset_id=dataset.id, question="Q?", expected_answer="A", expected_documents=[{"document_id": str(uuid.uuid4())}]))
    await db_session.commit()

    job = await create_evaluation_job(db_session, dataset.id, model_config={"retrieval_config": {"top_k": 12, "strategy": "vector", "mmr": True}})
    await db_session.commit()
    job = await run_evaluation_job(db_session, job.id)

    kwargs = search_mock.await_args.kwargs
    assert kwargs["top_k"] == 12 and kwargs["strategy"] == "vector_only"
    assert kwargs["org_settings"]["mmr_enabled"] is True
    # default: the whole corpus is searched (the ground-truth restriction is opt-in)
    assert "document_ids" not in kwargs
    assert job.results["corpus_constrained"] is False
    assert job.results["retrieval_config"] == {"top_k": 12, "strategy": "vector", "mmr": True}


async def test_the_ground_truth_corpus_restriction_is_opt_in_and_recorded_on_the_job(monkeypatch, db_session):
    from api.services.evaluation_jobs import create_evaluation_job, run_evaluation_job

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr(settings, "EVALUATION_RESTRICT_RETRIEVAL_TO_GROUND_TRUTH_DOCS", True)
    response = ModelResponse(choices=[Choices(message=Message(content="An answer.", role="assistant"), index=0, finish_reason="stop")])
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=response))
    search_mock = AsyncMock(return_value=[])
    monkeypatch.setattr("api.services.evaluation_results.search_with_context", search_mock)

    dataset = await _make_dataset(db_session)
    expected_doc = uuid.uuid4()
    db_session.add(EvaluationQuestion(dataset_id=dataset.id, question="Q?", expected_answer="A", expected_documents=[{"document_id": str(expected_doc)}]))
    await db_session.commit()
    job = await create_evaluation_job(db_session, dataset.id)
    await db_session.commit()
    job = await run_evaluation_job(db_session, job.id)

    assert search_mock.await_args.kwargs["document_ids"] == [expected_doc]
    assert job.results["corpus_constrained"] is True


# ------------------------------------------------------- apply + rollback (explicit)


async def _make_agent(db_session, org_id, config):
    agent = Agent(organization_id=org_id, name="a", system_prompt="x", model_config_json={}, knowledge_base_config=config)
    db_session.add(agent)
    await db_session.commit()
    return agent


async def test_apply_returns_the_previous_config_and_rollback_restores_it_exactly(db_session):
    dataset = await _make_dataset(db_session)
    agent = await _make_agent(db_session, dataset.organization_id, {"top_k": 5, "score_threshold": 0.4})

    applied = await apply_retrieval_recommendation(db_session, dataset.organization_id, agent.id, {"strategy": "hybrid_reranked", "top_k": 10})
    assert applied["previous"] == {"top_k": 5, "score_threshold": 0.4}
    assert applied["current"] == {"top_k": 10, "score_threshold": 0.4, "strategy": "hybrid_reranked"}

    rolled_back = await apply_retrieval_recommendation(db_session, dataset.organization_id, agent.id, applied["previous"], replace=True)
    assert rolled_back["current"] == {"top_k": 5, "score_threshold": 0.4}


async def test_apply_validates_and_never_touches_another_organizations_agent(db_session):
    dataset = await _make_dataset(db_session)
    other = await _make_dataset(db_session)
    foreign = await _make_agent(db_session, other.organization_id, {"top_k": 5})

    with pytest.raises(AgentKnowledgeBaseError):
        await apply_retrieval_recommendation(db_session, dataset.organization_id, foreign.id, {"topk": 1})
    with pytest.raises(ValueError, match="Agent not found"):
        await apply_retrieval_recommendation(db_session, dataset.organization_id, foreign.id, {"top_k": 9})
    await db_session.refresh(foreign)
    assert foreign.knowledge_base_config == {"top_k": 5}


# ------------------------------------------------------------------- the routes


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _owner_with_org(client, register_payload):
    token = (await client.post("/auth/register", json={"email": register_payload["email"], "password": register_payload["password"], "accept_terms": True})).json()["access_token"]
    org_id = (await client.post("/organizations", json={"name": "Route Org"}, headers=_auth_header(token))).json()["id"]
    return token, org_id


async def test_both_evolution_routes_refuse_another_organizations_dataset(client, db_session, register_payload):
    token, org_id = await _owner_with_org(client, register_payload)
    foreign = await _make_dataset(db_session)

    prompt_cycle = await client.post(
        f"/organizations/{org_id}/evolution/run", json={"dataset_id": str(foreign.id), "llm_provider": "anthropic"}, headers=_auth_header(token),
    )
    retrieval_cycle = await client.post(
        f"/organizations/{org_id}/evolution/retrieval/run", json={"dataset_id": str(foreign.id)}, headers=_auth_header(token),
    )

    assert prompt_cycle.status_code == 404 and retrieval_cycle.status_code == 404


async def test_the_apply_route_applies_audits_and_supports_rollback(client, db_session, register_payload):
    token, org_id = await _owner_with_org(client, register_payload)
    agent = await _make_agent(db_session, uuid.UUID(org_id), {"top_k": 5})
    url = f"/organizations/{org_id}/agents/{agent.id}/retrieval-config/apply"

    applied = await client.post(url, json={"config": {"top_k": 10}}, headers=_auth_header(token))
    rolled_back = await client.post(url, json={"config": applied.json()["previous"], "replace": True}, headers=_auth_header(token))
    invalid = await client.post(url, json={"config": {"topk": 1}}, headers=_auth_header(token))
    missing = await client.post(f"/organizations/{org_id}/agents/{uuid.uuid4()}/retrieval-config/apply", json={"config": {"top_k": 3}}, headers=_auth_header(token))

    assert applied.status_code == 200 and applied.json()["current"] == {"top_k": 10}
    assert rolled_back.json()["current"] == {"top_k": 5}
    assert invalid.status_code == 400 and missing.status_code == 404


async def test_the_retrieval_cycle_route_refuses_a_zero_balance_before_running_any_job(monkeypatch, client, db_session, register_payload):
    from sqlalchemy import select

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

    response = await client.post(f"/organizations/{org_id}/evolution/retrieval/run", json={"dataset_id": str(dataset.id)}, headers=_auth_header(token))

    assert response.status_code == 402
    create.assert_not_awaited()


# ------------------------------------------- Hardening Mission §12: several datasets per recommendation


def _cycle_result(deltas: list[float], accepted: list[bool]) -> dict:
    return {
        "baseline_job_id": uuid.uuid4(), "decision": "candidate_recommended", "corpus_constrained": False,
        "candidates": [
            {"config": cfg, "job_id": uuid.uuid4(), "accepted": ok, "target_delta": d, "reasons": [] if ok else ["mrr regressed by -0.2000 (allowed: 0.0500)"], "comparison": {}}
            for cfg, d, ok in zip([{"top_k": 10}, {"strategy": "hybrid_reranked"}], deltas, accepted)
        ],
    }


async def test_a_candidate_must_be_accepted_on_every_dataset_to_be_recommended(db_session):
    from api.services.rag_evolution_engine import run_multi_dataset_retrieval_evolution

    ds1, ds2 = await _make_dataset(db_session), None
    ds2 = EvaluationDataset(organization_id=ds1.organization_id, name="second")
    db_session.add(ds2)
    await db_session.commit()
    # candidate 0: +0.30 on dataset 1 but rejected on dataset 2 (overfitted); candidate 1: modest but accepted on both
    cycles = [_cycle_result([0.30, 0.05], [True, True]), _cycle_result([0.01, 0.07], [False, True])]

    with patch("api.services.rag_evolution_engine.run_retrieval_evolution_cycle", AsyncMock(side_effect=cycles)):
        result = await run_multi_dataset_retrieval_evolution(db_session, [ds1.id, ds2.id], [{"top_k": 10}, {"strategy": "hybrid_reranked"}])

    assert result["datasets_evaluated"] == 2 and result["decision"] == "candidate_recommended"
    assert result["recommended_config"] == {"strategy": "hybrid_reranked"}
    first, second = result["candidates"]
    assert first["accepted_on_all"] is False and any(r.startswith("dataset 2:") for r in first["reasons"])
    assert second["accepted_on_all"] is True and second["mean_target_delta"] == pytest.approx(0.06)


async def test_the_baseline_is_kept_when_no_candidate_is_accepted_on_all_datasets(db_session):
    from api.services.rag_evolution_engine import run_multi_dataset_retrieval_evolution

    ds1 = await _make_dataset(db_session)
    ds2 = EvaluationDataset(organization_id=ds1.organization_id, name="second")
    db_session.add(ds2)
    await db_session.commit()
    cycles = [_cycle_result([0.2, 0.2], [True, True]), _cycle_result([0.2, 0.2], [False, False])]

    with patch("api.services.rag_evolution_engine.run_retrieval_evolution_cycle", AsyncMock(side_effect=cycles)):
        result = await run_multi_dataset_retrieval_evolution(db_session, [ds1.id, ds2.id], [{"top_k": 10}, {"strategy": "hybrid_reranked"}])

    assert result["decision"] == "baseline_kept" and result["recommended_config"] is None


async def test_multi_dataset_evolution_refuses_mixed_organizations_and_unknown_datasets(db_session):
    from api.services.rag_evolution_engine import run_multi_dataset_retrieval_evolution

    ds_a, ds_b = await _make_dataset(db_session), await _make_dataset(db_session)
    with pytest.raises(ValueError, match="same organization"):
        await run_multi_dataset_retrieval_evolution(db_session, [ds_a.id, ds_b.id], [{"top_k": 10}])
    with pytest.raises(ValueError, match="not found"):
        await run_multi_dataset_retrieval_evolution(db_session, [ds_a.id, uuid.uuid4()], [{"top_k": 10}])
    with pytest.raises(ValueError, match="at least one"):
        await run_multi_dataset_retrieval_evolution(db_session, [], [{"top_k": 10}])


async def test_the_multi_route_refuses_a_foreign_extra_dataset_before_running_anything(monkeypatch, client, db_session, register_payload):
    token, org_id = await _owner_with_org(client, register_payload)
    mine = EvaluationDataset(organization_id=uuid.UUID(org_id), name="mine")
    db_session.add(mine)
    await db_session.commit()
    foreign = await _make_dataset(db_session)
    create = AsyncMock()
    monkeypatch.setattr("api.services.evaluation_jobs.create_evaluation_job", create)

    response = await client.post(
        f"/organizations/{org_id}/evolution/retrieval/run-multi", json={"dataset_id": str(mine.id), "extra_dataset_ids": [str(foreign.id)]}, headers=_auth_header(token),
    )

    assert response.status_code == 404
    create.assert_not_awaited()

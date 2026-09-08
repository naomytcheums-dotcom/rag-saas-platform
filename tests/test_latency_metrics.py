"""Partie 7.2.13 -- latency benchmarking. Fast SQLite suite;
litellm/search_with_context mocked at the same boundary as
tests/test_evaluation_results.py. Warmup/measurement run counts kept
small via monkeypatch to avoid an unnecessarily slow real suite."""

import uuid
from unittest.mock import AsyncMock

import litellm
from litellm.types.utils import Choices, Message, ModelResponse

from api.config import settings
from api.models.evaluation import EvaluationDataset, EvaluationQuestion, EvaluationResult
from api.models.organization import Organization
from api.services.latency_metrics import get_latency_distribution, get_latency_summary, measure_latency


def _real_response(text: str) -> ModelResponse:
    message = Message(content=text, role="assistant")
    choice = Choices(message=message, index=0, finish_reason="stop")
    return ModelResponse(choices=[choice])


async def _make_org(db_session, name):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


async def _make_question(db_session, org_id):
    dataset = EvaluationDataset(organization_id=org_id, name="D")
    db_session.add(dataset)
    await db_session.flush()
    question = EvaluationQuestion(dataset_id=dataset.id, question="Why is the sky blue?")
    db_session.add(question)
    await db_session.commit()
    return dataset, question


async def test_measure_latency_returns_a_real_percentile_distribution(monkeypatch, db_session):
    """Validation criterion: la mesure de latence fonctionne."""
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr(settings, "LATENCY_WARMUP_RUNS", 1)
    monkeypatch.setattr(settings, "LATENCY_MEASUREMENT_RUNS", 2)
    monkeypatch.setattr("api.services.evaluation_results.search_with_context", AsyncMock(return_value=[]))
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("An answer.")))

    org = await _make_org(db_session, "Latency Org")
    await db_session.commit()
    _dataset, question = await _make_question(db_session, org.id)

    result = await measure_latency(db_session, question.id)

    assert result["sample_size"] == 2
    assert result["p50"] is not None
    assert result["min"] <= result["p50"] <= result["max"]


async def test_measure_latency_excludes_a_real_timed_out_run(monkeypatch, db_session):
    """Validation criterion: robustesse -- un appel échoue (timeout)."""
    import asyncio

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr(settings, "LATENCY_WARMUP_RUNS", 0)
    monkeypatch.setattr(settings, "LATENCY_MEASUREMENT_RUNS", 1)
    monkeypatch.setattr(settings, "EVALUATION_TIMEOUT", 0.05)

    async def _hang(*args, **kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr("api.services.evaluation_results.search_with_context", _hang)

    org = await _make_org(db_session, "Latency Timeout Org")
    await db_session.commit()
    _dataset, question = await _make_question(db_session, org.id)

    result = await measure_latency(db_session, question.id)
    assert result["sample_size"] == 0
    assert result["p50"] is None


async def test_get_latency_summary_and_distribution_aggregate_real_stored_results(db_session):
    """Validation criterion: robustesse -- zéro cout réel additionnel,
    réutilise `EvaluationResult.latency_ms` déjà stocké."""
    org = await _make_org(db_session, "Latency Summary Org")
    await db_session.commit()
    dataset, question = await _make_question(db_session, org.id)
    for latency in (100, 200, 300):
        db_session.add(EvaluationResult(
            question_id=question.id, model_config_json={}, retrieved_documents=[], retrieved_chunks=[],
            actual_answer="a", metrics={}, latency_ms=latency,
        ))
    await db_session.commit()

    summary = await get_latency_summary(db_session, dataset.id)
    assert summary["sample_size"] == 3
    assert summary["avg"] == 200.0

    distribution = await get_latency_distribution(db_session, dataset.id)
    assert distribution["values"] == [100.0, 200.0, 300.0]

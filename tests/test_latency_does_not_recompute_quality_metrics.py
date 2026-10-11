"""Partie 7.2.13 -- measure_latency only needs the timing of each run.

`run_evaluation` ends with `extend_evaluation_metrics`, which recomputes the quality metrics (faithfulness, hallucination, semantic similarity, cost)
of EVERY stored result of the question. Called 4 to 8 times by measure_latency that grew quadratically and loaded an embedding model inside the
LATENCY_TIMEOUT budget: on a busy machine the whole budget was spent there, every measurement was skipped and sample_size came back as 0
(tests/test_latency_metrics.py failed in the full parts 10 and 11 runs, and passed alone)."""

import uuid
from unittest.mock import AsyncMock

import litellm
from litellm.types.utils import Choices, Message, ModelResponse

from api.config import settings
from api.models.evaluation import EvaluationDataset, EvaluationQuestion
from api.models.organization import Organization
from api.services import evaluation_results
from api.services.evaluation_results import run_evaluation
from api.services.latency_metrics import measure_latency


def _response(text: str) -> ModelResponse:
    return ModelResponse(choices=[Choices(message=Message(content=text, role="assistant"), index=0, finish_reason="stop")])


async def _question(db_session):
    org = Organization(name="Latency Org", slug=f"latency-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    dataset = EvaluationDataset(organization_id=org.id, name="D")
    db_session.add(dataset)
    await db_session.flush()
    question = EvaluationQuestion(dataset_id=dataset.id, question="Why is the sky blue?")
    db_session.add(question)
    await db_session.commit()
    return question


def _patch_llm(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr("api.services.evaluation_results.search_with_context", AsyncMock(return_value=[]))
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_response("An answer.")))


async def test_measure_latency_never_recomputes_the_quality_metrics(monkeypatch, db_session):
    _patch_llm(monkeypatch)
    monkeypatch.setattr(settings, "LATENCY_WARMUP_RUNS", 2)
    monkeypatch.setattr(settings, "LATENCY_MEASUREMENT_RUNS", 3)
    calls = []

    async def spy(db, question_id, k=None):
        calls.append(question_id)
        return []

    monkeypatch.setattr(evaluation_results, "extend_evaluation_metrics", spy)
    question = await _question(db_session)

    result = await measure_latency(db_session, question.id)

    assert result["sample_size"] == 3
    assert calls == [], "measure_latency recomputed the quality metrics"


async def test_run_evaluation_still_computes_the_metrics_by_default(monkeypatch, db_session):
    _patch_llm(monkeypatch)
    calls = []

    async def spy(db, question_id, k=None):
        calls.append(question_id)
        return []

    monkeypatch.setattr(evaluation_results, "extend_evaluation_metrics", spy)
    question = await _question(db_session)

    assert await run_evaluation(db_session, question.id) is not None
    assert calls == [question.id]

    calls.clear()
    assert await run_evaluation(db_session, question.id, compute_metrics=False) is not None
    assert calls == []

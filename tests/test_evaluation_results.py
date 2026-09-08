"""Partie 7.2.1-7.2.9 -- real evaluation runs and metrics. Fast SQLite
suite; litellm/search_with_context mocked at the same clean boundary
as tests/test_generation.py -- real embedding-model load time (used by
calculate_answer_relevance's own semantic_similarity factor) is NOT
mocked away, same precedent as tests/test_answer_quality_metrics.py."""

import asyncio
import uuid
from unittest.mock import AsyncMock

import litellm
import pytest
from litellm.types.utils import Choices, Message, ModelResponse

from api.config import settings
from api.models.evaluation import EvaluationDataset, EvaluationQuestion, EvaluationResult
from api.models.organization import Organization
from api.services.evaluation_results import extend_evaluation_metrics, get_evaluation_results, get_metrics_summary, run_evaluation


def _real_response(text: str) -> ModelResponse:
    message = Message(content=text, role="assistant")
    choice = Choices(message=message, index=0, finish_reason="stop")
    return ModelResponse(choices=[choice])


@pytest.fixture(autouse=True)
def _configure_key(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")


async def _make_org(db_session, name):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


async def _make_question(db_session, org_id, expected_documents=None):
    dataset = EvaluationDataset(organization_id=org_id, name="D")
    db_session.add(dataset)
    await db_session.flush()
    question = EvaluationQuestion(dataset_id=dataset.id, question="Why is the sky blue?", expected_documents=expected_documents)
    db_session.add(question)
    await db_session.commit()
    return dataset, question


def _fake_chunks(document_id="doc-a"):
    return [{"chunk_id": str(uuid.uuid4()), "document_id": document_id, "content": "The sky scatters blue light.", "score": 0.9,
             "document_name": "physics.pdf", "file_type": "application/pdf"}]


# --------------------------------------- run_evaluation --


async def test_run_evaluation_persists_a_real_result_with_real_metrics(monkeypatch, db_session):
    """Validation criterion (7.2.1): les résultats d'évaluation sont stockés."""
    monkeypatch.setattr("api.services.evaluation_results.search_with_context", AsyncMock(return_value=_fake_chunks("doc-a")))
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("The sky is blue because of Rayleigh scattering.")))

    org = await _make_org(db_session, "Eval Results Org")
    await db_session.commit()
    _dataset, question = await _make_question(db_session, org.id, expected_documents=[{"document_id": "doc-a"}])

    result = await run_evaluation(db_session, question.id)
    await db_session.commit()

    assert result is not None
    assert result.actual_answer == "The sky is blue because of Rayleigh scattering."
    assert result.retrieved_documents == [{"document_id": "doc-a", "score": 0.9}]
    assert result.latency_ms >= 0
    assert result.metrics["recall_at_1"] == 1.0
    assert result.metrics["mrr"] == 1.0
    assert set(result.metrics["faithfulness_factors"]) == {"claim_support", "source_alignment", "context_usage", "hallucination_absence"}
    assert set(result.metrics["answer_relevance_factors"]) == {"question_coverage", "key_terms_presence", "semantic_similarity", "length_adequacy"}


async def test_run_evaluation_is_honestly_none_for_an_unknown_question(db_session):
    """Validation criterion: robustesse -- question inconnue."""
    assert await run_evaluation(db_session, uuid.uuid4()) is None


async def test_run_evaluation_records_a_real_honest_timeout(monkeypatch, db_session):
    """Validation criterion: performance -- le timeout est respecté,
    same real 'hang forever, never sleep' simulation as
    tests/test_agent_orchestrator.py's own test_run_agent_times_out."""
    monkeypatch.setattr(settings, "EVALUATION_TIMEOUT", 0.05)

    async def _hang(*args, **kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr("api.services.evaluation_results.search_with_context", _hang)

    org = await _make_org(db_session, "Eval Timeout Org")
    await db_session.commit()
    _dataset, question = await _make_question(db_session, org.id)

    result = await run_evaluation(db_session, question.id)
    await db_session.commit()

    assert result is not None
    assert result.actual_answer == ""
    assert result.retrieved_documents == []


async def test_run_evaluation_passes_a_real_candidate_model_config(monkeypatch, db_session):
    """Validation criterion: cohérence -- teste une config candidate,
    pas la config par défaut de l'organisation."""
    mock_acompletion = AsyncMock(return_value=_real_response("ok"))
    monkeypatch.setattr("api.services.evaluation_results.search_with_context", AsyncMock(return_value=[]))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    org = await _make_org(db_session, "Eval Candidate Org")
    await db_session.commit()
    _dataset, question = await _make_question(db_session, org.id)

    result = await run_evaluation(db_session, question.id, model_config={"temperature": 0.9})
    await db_session.commit()

    assert result.model_config_json == {"temperature": 0.9}
    assert mock_acompletion.call_args.kwargs["temperature"] == 0.9


# --------------------------------------- extend_evaluation_metrics --


async def test_extend_evaluation_metrics_rescales_after_ground_truth_changes(monkeypatch, db_session):
    """Validation criterion: cohérence -- une évaluation déjà enregistrée
    reflète la ground truth ACTUELLE de la question, pas celle au
    moment du run."""
    monkeypatch.setattr("api.services.evaluation_results.search_with_context", AsyncMock(return_value=_fake_chunks("doc-a")))
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("An answer.")))

    org = await _make_org(db_session, "Eval Rescale Org")
    await db_session.commit()
    _dataset, question = await _make_question(db_session, org.id, expected_documents=None)

    result = await run_evaluation(db_session, question.id)
    await db_session.commit()
    assert result.metrics["recall_at_1"] == 0.0

    question.expected_documents = [{"document_id": "doc-a"}]
    await db_session.flush()
    await extend_evaluation_metrics(db_session, question.id)
    await db_session.commit()
    await db_session.refresh(result)

    assert result.metrics["recall_at_1"] == 1.0


async def test_extend_evaluation_metrics_is_honestly_empty_for_an_unknown_question(db_session):
    """Validation criterion: robustesse."""
    assert await extend_evaluation_metrics(db_session, uuid.uuid4()) == []


# --------------------------------------- get_evaluation_results / get_metrics_summary --


async def test_get_evaluation_results_paginates_real_results(db_session):
    """Validation criterion (7.2.1): résultats paginés."""
    org = await _make_org(db_session, "Eval Pagination Org")
    await db_session.commit()
    _dataset, question = await _make_question(db_session, org.id)
    for i in range(3):
        db_session.add(EvaluationResult(
            question_id=question.id, model_config_json={}, retrieved_documents=[], retrieved_chunks=[],
            actual_answer=f"a{i}", metrics={}, latency_ms=1,
        ))
    await db_session.commit()

    page = await get_evaluation_results(db_session, question.id, limit=2, offset=0)
    assert page["total"] == 3
    assert len(page["items"]) == 2


async def test_get_metrics_summary_reuses_retrieval_metrics(db_session):
    """Validation criterion: cohérence -- thin reuse of
    retrieval_metrics.summarize_metric, not a second aggregation."""
    org = await _make_org(db_session, "Eval Summary Org")
    await db_session.commit()
    _dataset, question = await _make_question(db_session, org.id)
    db_session.add(EvaluationResult(
        question_id=question.id, model_config_json={}, retrieved_documents=[], retrieved_chunks=[],
        actual_answer="a", metrics={"recall_at_1": 1.0}, latency_ms=1,
    ))
    await db_session.commit()

    summary = await get_metrics_summary(db_session, _dataset.id, "recall_at_1")
    assert summary == {"metric": "recall_at_1", "count": 1, "average": 1.0, "min": 1.0, "max": 1.0}

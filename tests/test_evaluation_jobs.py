"""Partie 7.3.1 -- automatic evaluation jobs. Fast SQLite suite;
litellm/search_with_context mocked at the same boundary as
tests/test_evaluation_results.py."""

import uuid
from unittest.mock import AsyncMock

import litellm
import pytest
from sqlalchemy import select
from litellm.types.utils import Choices, Message, ModelResponse

from api.config import settings
from api.models.evaluation import EvaluationDataset, EvaluationFailureCategory, EvaluationJobStatus, EvaluationQuestion, EvaluationResult
from api.models.organization import Organization
from api.services.evaluation_jobs import (
    cancel_evaluation_job, categorize_job_failures, create_evaluation_job, get_evaluation_job_results,
    get_job_failures, list_evaluation_jobs, run_evaluation_job,
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


async def _make_dataset(db_session, org_id, question_count=3):
    dataset = EvaluationDataset(organization_id=org_id, name="D")
    db_session.add(dataset)
    await db_session.flush()
    for i in range(question_count):
        db_session.add(EvaluationQuestion(dataset_id=dataset.id, question=f"Question {i}?"))
    await db_session.commit()
    return dataset


async def test_create_evaluation_job_starts_pending(db_session):
    """Validation criterion: la création de job fonctionne."""
    org = await _make_org(db_session, "Eval Job Org")
    await db_session.commit()
    dataset = await _make_dataset(db_session, org.id)

    job = await create_evaluation_job(db_session, dataset.id)
    await db_session.commit()

    assert job.status == EvaluationJobStatus.pending
    assert job.progress == 0


async def test_run_evaluation_job_processes_every_real_question(monkeypatch, db_session):
    """Validation criterion: l'exécution de job fonctionne."""
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr("api.services.evaluation_results.search_with_context", AsyncMock(return_value=[]))
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("An answer.")))

    org = await _make_org(db_session, "Eval Job Run Org")
    await db_session.commit()
    dataset = await _make_dataset(db_session, org.id, question_count=3)
    job = await create_evaluation_job(db_session, dataset.id)
    await db_session.commit()

    updated = await run_evaluation_job(db_session, job.id)

    assert updated.status == EvaluationJobStatus.completed
    assert updated.total_questions == 3
    assert updated.completed_questions == 3
    assert updated.progress == 100
    assert len(updated.results["result_ids"]) == 3

    results = await get_evaluation_job_results(db_session, job.id)
    assert results["total"] == 3
    assert all(r.evaluation_job_id == job.id for r in results["items"])


async def test_run_evaluation_job_survives_one_real_question_failing(monkeypatch, db_session):
    """Validation criterion: robustesse -- une question échoue."""
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    call_count = {"n": 0}

    async def _flaky_search(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise RuntimeError("simulated real retrieval failure")
        return []

    monkeypatch.setattr("api.services.evaluation_results.search_with_context", _flaky_search)
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("An answer.")))

    org = await _make_org(db_session, "Eval Job Flaky Org")
    await db_session.commit()
    dataset = await _make_dataset(db_session, org.id, question_count=3)
    job = await create_evaluation_job(db_session, dataset.id)
    await db_session.commit()

    updated = await run_evaluation_job(db_session, job.id)

    assert updated.status == EvaluationJobStatus.completed
    assert updated.completed_questions == 3  # every real question was attempted
    assert updated.results["failed_questions"] == 1  # one real question's own failure honestly recorded

    # Phase 5, Étape 14 -- the failure is now a real, persisted row, not just a log line and a count.
    failures = await get_job_failures(db_session, job.id)
    assert len(failures) == 1
    assert failures[0].category == EvaluationFailureCategory.retrieval  # tagged by the real stage that raised
    assert "simulated real retrieval failure" in failures[0].error

    categories = await categorize_job_failures(db_session, job.id)
    assert categories[EvaluationFailureCategory.retrieval] == 1
    assert categories[EvaluationFailureCategory.generation] == 0


async def test_run_evaluation_job_categorizes_a_generation_stage_failure(monkeypatch, db_session):
    """A failure past the retrieval stage is tagged 'generation', not lumped into the same bucket as a retrieval failure."""
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")

    async def _empty_search(*args, **kwargs):
        return []

    async def _broken_llm(*args, **kwargs):
        raise RuntimeError("simulated real generation failure")

    monkeypatch.setattr("api.services.evaluation_results.search_with_context", _empty_search)
    monkeypatch.setattr("api.services.evaluation_results.chat_completion_with_usage", _broken_llm)

    org = await _make_org(db_session, "Eval Job Generation Failure Org")
    await db_session.commit()
    dataset = await _make_dataset(db_session, org.id, question_count=1)
    job = await create_evaluation_job(db_session, dataset.id)
    await db_session.commit()

    updated = await run_evaluation_job(db_session, job.id)

    assert updated.status == EvaluationJobStatus.completed
    failures = await get_job_failures(db_session, job.id)
    assert len(failures) == 1
    assert failures[0].category == EvaluationFailureCategory.generation

    categories = await categorize_job_failures(db_session, job.id)
    assert categories[EvaluationFailureCategory.generation] == 1
    assert categories[EvaluationFailureCategory.retrieval] == 0


async def test_categorize_job_failures_counts_a_reliable_high_hallucination_result(monkeypatch, db_session):
    """A question that DID complete (a real EvaluationResult exists) but whose already-computed,
    reliable hallucination_rate is at/above the threshold counts as a real 'hallucination', a
    different real signal than an EvaluationFailure exception row."""
    org = await _make_org(db_session, "Eval Job Hallucination Org")
    await db_session.commit()
    dataset = await _make_dataset(db_session, org.id, question_count=1)
    job = await create_evaluation_job(db_session, dataset.id)
    await db_session.commit()
    question = (await db_session.scalars(select(EvaluationQuestion).where(EvaluationQuestion.dataset_id == dataset.id))).first()

    result = EvaluationResult(
        question_id=question.id, evaluation_job_id=job.id, model_config_json={}, retrieved_documents=[], retrieved_chunks=[],
        actual_answer="A confident, ungrounded answer.",
        metrics={"hallucination_rate": 0.9, "hallucination_rate_reliable": True}, latency_ms=10,
    )
    db_session.add(result)
    await db_session.commit()

    categories = await categorize_job_failures(db_session, job.id)
    assert categories["hallucination"] == 1


async def test_run_evaluation_job_is_honestly_none_for_an_unknown_job(db_session):
    """Validation criterion: robustesse."""
    assert await run_evaluation_job(db_session, uuid.uuid4()) is None


async def test_cancel_evaluation_job_before_it_ever_ran_is_never_processed(db_session):
    """Validation criterion: l'annulation fonctionne -- a real,
    already-cancelled job is honestly refused, never silently run
    anyway (e.g. a real race with a Celery worker that only picks the
    real task up after the real cancel request already landed)."""
    org = await _make_org(db_session, "Eval Job Cancel Org")
    await db_session.commit()
    dataset = await _make_dataset(db_session, org.id, question_count=3)
    job = await create_evaluation_job(db_session, dataset.id)
    await db_session.commit()

    cancelled = await cancel_evaluation_job(db_session, job.id)
    await db_session.commit()
    assert cancelled.status == EvaluationJobStatus.cancelled

    with pytest.raises(ValueError):
        await run_evaluation_job(db_session, job.id)


async def test_cancel_evaluation_job_stops_a_real_mid_run_loop(monkeypatch, db_session):
    """Validation criterion: l'annulation fonctionne -- a real,
    COOPERATIVE cancel requested DURING a run (simulated: the mocked
    search itself cancels the job, standing in for a real, concurrent
    cancel request landing mid-run) stops the real loop before every
    real question is processed."""
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    org = await _make_org(db_session, "Eval Job Mid Cancel Org")
    await db_session.commit()
    dataset = await _make_dataset(db_session, org.id, question_count=3)
    job = await create_evaluation_job(db_session, dataset.id)
    await db_session.commit()

    call_count = {"n": 0}

    async def _search_then_cancel(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            await cancel_evaluation_job(db_session, job.id)
            await db_session.commit()
        return []

    monkeypatch.setattr("api.services.evaluation_results.search_with_context", _search_then_cancel)
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("An answer.")))

    updated = await run_evaluation_job(db_session, job.id)

    assert updated.status == EvaluationJobStatus.cancelled
    assert updated.completed_questions < 3


async def test_cancel_evaluation_job_rejects_an_already_completed_job(monkeypatch, db_session):
    """Validation criterion: robustesse."""
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr("api.services.evaluation_results.search_with_context", AsyncMock(return_value=[]))
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("An answer.")))

    org = await _make_org(db_session, "Eval Job Done Org")
    await db_session.commit()
    dataset = await _make_dataset(db_session, org.id, question_count=1)
    job = await create_evaluation_job(db_session, dataset.id)
    await db_session.commit()
    await run_evaluation_job(db_session, job.id)

    with pytest.raises(ValueError):
        await cancel_evaluation_job(db_session, job.id)


async def test_list_evaluation_jobs_paginates(db_session):
    org = await _make_org(db_session, "Eval Job List Org")
    await db_session.commit()
    dataset = await _make_dataset(db_session, org.id, question_count=0)
    for _ in range(3):
        await create_evaluation_job(db_session, dataset.id)
    await db_session.commit()

    page = await list_evaluation_jobs(db_session, dataset.id, limit=2, offset=0)
    assert page["total"] == 3
    assert len(page["items"]) == 2

"""Partie 7.3.3 -- regression detection. Fast, pure-DB suite (no real
LLM calls needed -- EvaluationResult rows are built directly with
pre-set .metrics dicts, since detect_regressions only ever reads
already-stored metric values)."""

import uuid

from api.config import settings
from api.models.evaluation import EvaluationDataset, EvaluationJob, EvaluationQuestion, EvaluationResult
from api.models.organization import Organization
from api.services.regression_detection import detect_regressions, get_regression_summary, get_regressions, resolve_regression


async def _make_org(db_session, name):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


async def _make_job_with_results(db_session, dataset_id, question_id, metric_values: list[dict]) -> EvaluationJob:
    job = EvaluationJob(dataset_id=dataset_id, status="completed", total_questions=len(metric_values), completed_questions=len(metric_values))
    db_session.add(job)
    await db_session.flush()
    result_ids = []
    for metrics in metric_values:
        result = EvaluationResult(
            question_id=question_id, model_config_json={}, retrieved_documents=[], retrieved_chunks=[],
            actual_answer="a", metrics=metrics, latency_ms=1, evaluation_job_id=job.id,
        )
        db_session.add(result)
        await db_session.flush()
        result_ids.append(str(result.id))
    job.results = {"result_ids": result_ids}
    await db_session.commit()
    return job


def _n_samples(value: float, n: int = 10) -> list[dict]:
    return [{"faithfulness": value} for _ in range(n)]


async def test_detect_regressions_flags_a_real_faithfulness_drop(db_session):
    """Validation criterion: la détection de régression fonctionne."""
    org = await _make_org(db_session, "Regression Detect Org")
    await db_session.commit()
    dataset = EvaluationDataset(organization_id=org.id, name="D")
    db_session.add(dataset)
    await db_session.flush()
    question = EvaluationQuestion(dataset_id=dataset.id, question="Q?")
    db_session.add(question)
    await db_session.commit()

    previous_job = await _make_job_with_results(db_session, dataset.id, question.id, _n_samples(0.9))
    current_job = await _make_job_with_results(db_session, dataset.id, question.id, _n_samples(0.5))  # a real, big drop

    detections = await detect_regressions(db_session, current_job.id, previous_job.id)
    await db_session.commit()

    faithfulness = next(d for d in detections if d.metric == "faithfulness")
    assert faithfulness.severity == "critical"
    assert faithfulness.previous_value == 0.9
    assert faithfulness.current_value == 0.5


async def test_detect_regressions_ignores_a_real_improvement(db_session):
    """Validation criterion: les seuils sont respectés -- une
    amélioration n'est jamais une régression."""
    org = await _make_org(db_session, "Regression Improve Org")
    await db_session.commit()
    dataset = EvaluationDataset(organization_id=org.id, name="D")
    db_session.add(dataset)
    await db_session.flush()
    question = EvaluationQuestion(dataset_id=dataset.id, question="Q?")
    db_session.add(question)
    await db_session.commit()

    previous_job = await _make_job_with_results(db_session, dataset.id, question.id, _n_samples(0.5))
    current_job = await _make_job_with_results(db_session, dataset.id, question.id, _n_samples(0.9))

    detections = await detect_regressions(db_session, current_job.id, previous_job.id)
    assert not any(d.metric == "faithfulness" for d in detections)


async def test_detect_regressions_honestly_ignores_insufficient_samples(monkeypatch, db_session):
    """Validation criterion: robustesse -- échantillons insuffisants."""
    monkeypatch.setattr(settings, "REGRESSION_MIN_SAMPLES", 10)
    org = await _make_org(db_session, "Regression Thin Org")
    await db_session.commit()
    dataset = EvaluationDataset(organization_id=org.id, name="D")
    db_session.add(dataset)
    await db_session.flush()
    question = EvaluationQuestion(dataset_id=dataset.id, question="Q?")
    db_session.add(question)
    await db_session.commit()

    previous_job = await _make_job_with_results(db_session, dataset.id, question.id, _n_samples(0.9, n=2))
    current_job = await _make_job_with_results(db_session, dataset.id, question.id, _n_samples(0.1, n=2))

    detections = await detect_regressions(db_session, current_job.id, previous_job.id)
    assert detections == []


async def test_detect_regressions_flags_an_increase_for_a_real_lower_is_better_metric(db_session):
    """Validation criterion: précision -- les seuils sont pertinents
    (hallucination_rate: une hausse est une régression, pas une baisse)."""
    org = await _make_org(db_session, "Regression Lower Better Org")
    await db_session.commit()
    dataset = EvaluationDataset(organization_id=org.id, name="D")
    db_session.add(dataset)
    await db_session.flush()
    question = EvaluationQuestion(dataset_id=dataset.id, question="Q?")
    db_session.add(question)
    await db_session.commit()

    previous_job = await _make_job_with_results(db_session, dataset.id, question.id, [{"hallucination_rate": 0.1} for _ in range(10)])
    current_job = await _make_job_with_results(db_session, dataset.id, question.id, [{"hallucination_rate": 0.4} for _ in range(10)])

    detections = await detect_regressions(db_session, current_job.id, previous_job.id)
    hallucination = next(d for d in detections if d.metric == "hallucination_rate")
    assert hallucination.severity in ("high", "critical")


async def test_detect_regressions_is_honestly_empty_for_an_unknown_job(db_session):
    """Validation criterion: robustesse."""
    assert await detect_regressions(db_session, uuid.uuid4(), uuid.uuid4()) == []


async def test_resolve_regression_marks_it_resolved(db_session):
    """Validation criterion: la résolution fonctionne."""
    org = await _make_org(db_session, "Regression Resolve Org")
    await db_session.commit()
    dataset = EvaluationDataset(organization_id=org.id, name="D")
    db_session.add(dataset)
    await db_session.flush()
    question = EvaluationQuestion(dataset_id=dataset.id, question="Q?")
    db_session.add(question)
    await db_session.commit()
    previous_job = await _make_job_with_results(db_session, dataset.id, question.id, _n_samples(0.9))
    current_job = await _make_job_with_results(db_session, dataset.id, question.id, _n_samples(0.5))
    detections = await detect_regressions(db_session, current_job.id, previous_job.id)
    await db_session.commit()
    detection = detections[0]

    resolved = await resolve_regression(db_session, detection.id, uuid.uuid4())
    await db_session.commit()
    assert resolved.resolved_at is not None


async def test_resolve_regression_is_honestly_none_for_an_unknown_regression(db_session):
    """Validation criterion: robustesse."""
    assert await resolve_regression(db_session, uuid.uuid4(), uuid.uuid4()) is None


async def test_get_regression_summary_counts_by_severity(db_session):
    org = await _make_org(db_session, "Regression Summary Org")
    await db_session.commit()
    dataset = EvaluationDataset(organization_id=org.id, name="D")
    db_session.add(dataset)
    await db_session.flush()
    question = EvaluationQuestion(dataset_id=dataset.id, question="Q?")
    db_session.add(question)
    await db_session.commit()
    previous_job = await _make_job_with_results(db_session, dataset.id, question.id, _n_samples(0.9))
    current_job = await _make_job_with_results(db_session, dataset.id, question.id, _n_samples(0.5))
    await detect_regressions(db_session, current_job.id, previous_job.id)
    await db_session.commit()

    summary = await get_regression_summary(db_session, dataset.id)
    assert summary["total"] >= 1
    assert summary["unresolved"] >= 1


async def test_get_regressions_paginates(db_session):
    org = await _make_org(db_session, "Regression List Org")
    await db_session.commit()
    dataset = EvaluationDataset(organization_id=org.id, name="D")
    db_session.add(dataset)
    await db_session.flush()
    question = EvaluationQuestion(dataset_id=dataset.id, question="Q?")
    db_session.add(question)
    await db_session.commit()
    previous_job = await _make_job_with_results(db_session, dataset.id, question.id, [{"faithfulness": 0.9, "recall_at_1": 0.9} for _ in range(10)])
    current_job = await _make_job_with_results(db_session, dataset.id, question.id, [{"faithfulness": 0.3, "recall_at_1": 0.2} for _ in range(10)])
    await detect_regressions(db_session, current_job.id, previous_job.id)
    await db_session.commit()

    page = await get_regressions(db_session, dataset.id, limit=1, offset=0)
    assert page["total"] >= 2
    assert len(page["items"]) == 1

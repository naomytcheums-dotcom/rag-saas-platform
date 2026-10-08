"""Hardening Mission, §13 (Guardian) -- real, focused tests for the new
`api/services/alerting.py::real_rag_quality_metric_value`, the real,
organization-scoped RAG-quality counterpart to the pre-existing infra
`real_metric_value` (cpu/memory/disk/celery/http_5xx). Real DB session,
real `EvaluationResult` rows -- no mocking, matching this module's own
"real metric from real data, never fabricated" discipline."""

import datetime as dt
import uuid

from api.models.alerting import AlertOperator, AlertRule, AlertSeverity
from api.models.evaluation import EvaluationDataset, EvaluationJob, EvaluationJobStatus, EvaluationQuestion, EvaluationResult
from api.models.organization import Organization
import pytest

from api.services import alerting
from api.services.alerting import check_alert_rules, real_rag_quality_metric_value


async def _make_completed_job_with_results(db_session, *, recall_values: list[float], status=EvaluationJobStatus.completed) -> tuple[uuid.UUID, uuid.UUID]:
    org = Organization(name="Guardian Org", slug=f"guardian-org-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    dataset = EvaluationDataset(organization_id=org.id, name="guardian-dataset")
    db_session.add(dataset)
    await db_session.flush()
    job = EvaluationJob(
        dataset_id=dataset.id, status=status, total_questions=len(recall_values), completed_questions=len(recall_values),
        completed_at=dt.datetime.now(dt.timezone.utc) if status == EvaluationJobStatus.completed else None,
    )
    db_session.add(job)
    await db_session.flush()
    for value in recall_values:
        question = EvaluationQuestion(dataset_id=dataset.id, question="Q")
        db_session.add(question)
        await db_session.flush()
        db_session.add(EvaluationResult(
            question_id=question.id, evaluation_job_id=job.id, model_config_json={}, retrieved_documents=[],
            retrieved_chunks=[], actual_answer="A", metrics={"recall_at_5": value}, latency_ms=100,
        ))
    await db_session.commit()
    return org.id, job.id


async def test_real_rag_quality_metric_value_returns_none_for_an_unknown_metric_name(db_session):
    org_id, _job_id = await _make_completed_job_with_results(db_session, recall_values=[0.9])
    assert await real_rag_quality_metric_value(db_session, "not_a_real_metric", org_id) is None


async def test_real_rag_quality_metric_value_returns_none_without_an_organization(db_session):
    assert await real_rag_quality_metric_value(db_session, "recall_at_5", None) is None


async def test_real_rag_quality_metric_value_returns_none_when_no_job_ever_completed(db_session):
    org = Organization(name="No Eval Org", slug=f"no-eval-org-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.commit()
    assert await real_rag_quality_metric_value(db_session, "recall_at_5", org.id) is None


async def test_real_rag_quality_metric_value_averages_the_real_latest_completed_job(db_session):
    org_id, _job_id = await _make_completed_job_with_results(db_session, recall_values=[0.6, 0.8, 1.0])
    value = await real_rag_quality_metric_value(db_session, "recall_at_5", org_id)
    assert value == pytest.approx(0.8)


async def test_real_rag_quality_metric_value_ignores_a_job_that_is_still_running(db_session):
    """A real, in-progress job's own partial results must never be
    averaged into a real alert decision -- only a genuinely COMPLETED
    run represents a real, final measurement."""
    org_id, _job_id = await _make_completed_job_with_results(db_session, recall_values=[0.1], status=EvaluationJobStatus.running)
    assert await real_rag_quality_metric_value(db_session, "recall_at_5", org_id) is None


async def test_check_alert_rules_triggers_a_real_incident_on_a_real_recall_regression(db_session):
    """Hardening Mission, §13 -- end-to-end: AGENTS.md's own documented
    GUARDIAN default (Recall@5 < 0.80 -> WARNING) fires for real off a
    real, computed average, with a real AlertHistory row persisted."""
    org_id, _job_id = await _make_completed_job_with_results(db_session, recall_values=[0.70, 0.72])
    db_session.add(AlertRule(
        organization_id=org_id, name="Recall@5 regression", metric="recall_at_5",
        operator=AlertOperator.lt, threshold=0.80, severity=AlertSeverity.medium, enabled=True,
    ))
    await db_session.commit()

    triggered = await check_alert_rules(db_session)
    await db_session.commit()

    matching = [h for h in triggered if "Recall@5 regression" in h.message]
    assert matching, f"expected a real triggered alert, got: {[t.message for t in triggered]}"
    assert matching[0].value_at_trigger == pytest.approx(0.71)


async def test_check_alert_rules_does_not_trigger_when_the_real_average_is_healthy(db_session):
    org_id, _job_id = await _make_completed_job_with_results(db_session, recall_values=[0.9, 0.95])
    db_session.add(AlertRule(
        organization_id=org_id, name="Healthy Recall@5", metric="recall_at_5",
        operator=AlertOperator.lt, threshold=0.80, severity=AlertSeverity.medium, enabled=True,
    ))
    await db_session.commit()

    triggered = await check_alert_rules(db_session)
    assert not any("Healthy Recall@5" in h.message for h in triggered)


async def test_alert_rule_endpoint_helper_reports_the_real_current_value(db_session):
    org_id, _job_id = await _make_completed_job_with_results(db_session, recall_values=[0.5])
    rule = AlertRule(
        organization_id=org_id, name="Test Button", metric="recall_at_5",
        operator=AlertOperator.lt, threshold=0.80, severity=AlertSeverity.medium, enabled=True,
    )
    db_session.add(rule)
    await db_session.commit()

    result = await alerting.test_alert_rule(db_session, rule.id)
    assert result["current_value"] == pytest.approx(0.5)
    assert result["would_trigger"] is True


# ------------------------------- Hardening Mission §13: explain + propose an action


async def _add_failures(db_session, job_id, dataset_id, category: str, count: int):
    from api.models.evaluation import EvaluationFailure

    for i in range(count):
        question = EvaluationQuestion(dataset_id=dataset_id, question=f"Failing {category} {i}", expected_answer="x")
        db_session.add(question)
        await db_session.flush()
        db_session.add(EvaluationFailure(evaluation_job_id=job_id, question_id=question.id, category=category, error="boom"))
    await db_session.commit()


async def test_a_breached_recall_alert_carries_the_autopsy_and_names_the_retrieval_evolution_step(db_session):
    org_id, job_id = await _make_completed_job_with_results(db_session, recall_values=[0.4, 0.5])
    dataset_id = (await db_session.get(EvaluationJob, job_id)).dataset_id
    await _add_failures(db_session, job_id, dataset_id, "retrieval", 3)
    await _add_failures(db_session, job_id, dataset_id, "generation", 1)
    db_session.add(AlertRule(organization_id=org_id, name="Recall guard", metric="recall_at_5", operator=AlertOperator.lt, threshold=0.8, severity=AlertSeverity.medium, enabled=True))
    await db_session.commit()

    triggered = await check_alert_rules(db_session)

    message = next(h.message for h in triggered if "Recall guard" in h.message)
    assert "retrieval=3" in message and "generation=1" in message
    assert f"/organizations/{org_id}/evolution/retrieval/run" in message
    assert "retrieval failures dominate" in message


async def test_the_suggestion_follows_the_dominant_measured_cause(db_session):
    org_id, job_id = await _make_completed_job_with_results(db_session, recall_values=[0.4])
    dataset_id = (await db_session.get(EvaluationJob, job_id)).dataset_id
    await _add_failures(db_session, job_id, dataset_id, "generation", 4)

    text = await alerting.explain_rag_quality_alert(db_session, "recall_at_5", org_id)

    assert "retrieval is not the dominant cause" in text and "evolution/retrieval/run" not in text


async def test_explanation_is_none_for_infra_metrics_unknown_orgs_and_orgs_without_a_completed_job(db_session):
    org_id, _ = await _make_completed_job_with_results(db_session, recall_values=[0.5])
    empty_org = Organization(name="Empty", slug=f"empty-{uuid.uuid4().hex[:8]}")
    db_session.add(empty_org)
    await db_session.commit()

    assert await alerting.explain_rag_quality_alert(db_session, "cpu_percent", org_id) is None
    assert await alerting.explain_rag_quality_alert(db_session, "recall_at_5", None) is None
    assert await alerting.explain_rag_quality_alert(db_session, "recall_at_5", empty_org.id) is None

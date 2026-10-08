"""P2C-5: real dataset/question/job/result/failure tenant hierarchy."""

from unittest.mock import AsyncMock, Mock

from sqlalchemy import func, select

from api.models.evaluation import (
    EvaluationDataset,
    EvaluationFailure,
    EvaluationJob,
    EvaluationQuestion,
    EvaluationResult,
)
from test_document_idor import denied, make_tenants, snapshot


async def test_evaluation_idor(client, db_session, monkeypatch):
    (owner, org_a, _), (attacker, _, _) = await make_tenants(
        client, db_session, monkeypatch, "evaluation"
    )
    dataset = EvaluationDataset(organization_id=org_a, name="private-dataset")
    db_session.add(dataset)
    await db_session.flush()
    question = EvaluationQuestion(
        dataset_id=dataset.id, question="private-question", expected_answer="private-answer"
    )
    job = EvaluationJob(dataset_id=dataset.id, status="pending", total_questions=1)
    db_session.add_all([question, job])
    await db_session.flush()
    result = EvaluationResult(
        question_id=question.id, evaluation_job_id=job.id, model_config_json={},
        retrieved_documents=[], retrieved_chunks=[], actual_answer="private-output",
        metrics={}, latency_ms=1,
    )
    failure = EvaluationFailure(
        evaluation_job_id=job.id, question_id=question.id, category="retrieval",
        error="private-failure",
    )
    db_session.add_all([result, failure])
    await db_session.commit()
    dataset_id, question_id, job_id = dataset.id, question.id, job.id
    baseline = await snapshot(db_session, dataset, question, job, result, failure)
    schedule, provider = Mock(), AsyncMock()
    monkeypatch.setattr("api.routers.evaluation_jobs.schedule_evaluation_job_processing", schedule)
    monkeypatch.setattr("api.routers.evaluation_results.run_evaluation", provider)
    control = await client.get(f"/datasets/{dataset_id}", headers=owner)
    assert control.status_code == 200, control.text
    control = await client.get(f"/jobs/{job_id}", headers=owner)
    assert control.status_code == 200, control.text
    violations = []
    for suffix in ("", "/questions", "/questions/export", "/jobs"):
        await denied(client, "GET", f"/datasets/{dataset_id}{suffix}", attacker, violations)
    await denied(
        client, "PATCH", f"/datasets/{dataset_id}", attacker, violations,
        json={"name": "attacker-rename"},
    )
    await denied(
        client, "PATCH", f"/questions/{question_id}", attacker, violations,
        json={"question": "attacker-question"},
    )
    await denied(
        client, "GET", f"/questions/{question_id}/results", attacker, violations
    )
    await denied(
        client, "POST", f"/questions/{question_id}/run", attacker, violations, json={}
    )
    await denied(
        client, "POST", f"/datasets/{dataset_id}/evaluate", attacker, violations, json={}
    )
    for suffix in ("", "/results", "/failures", "/failures/categories"):
        await denied(client, "GET", f"/jobs/{job_id}{suffix}", attacker, violations)
    await denied(client, "POST", f"/jobs/{job_id}/cancel", attacker, violations)
    await denied(client, "DELETE", f"/questions/{question_id}", attacker, violations)
    await denied(client, "DELETE", f"/datasets/{dataset_id}", attacker, violations)
    assert await snapshot(db_session, dataset, question, job, result, failure) == baseline
    assert await db_session.scalar(select(func.count()).select_from(EvaluationJob)) == 1
    schedule.assert_not_called()
    provider.assert_not_called()
    assert not violations, "\n".join(violations)

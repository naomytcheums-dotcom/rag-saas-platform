"""Phase 3 of the 2026-10-12 security audit (TEN-004): tenant isolation of the Eval Lab routes that tests/test_evaluation_idor.py does not reach.

Two real organizations (A, B). A owns a dataset, a question, a job, a result and a failure. B's owner calls every other route taking A's dataset or job
identifier. Every call must be refused (403/404), must not write anything, and must not start a job or call a provider.
Local SQLite fixtures only; no service involved.
"""

from unittest.mock import AsyncMock, Mock

from sqlalchemy import func, select

from api.models.evaluation import EvaluationDataset, EvaluationFailure, EvaluationJob, EvaluationQuestion, EvaluationResult
from test_document_idor import denied, make_tenants, snapshot

# (method, path template, json body). Bodies are plausible so that a validation error (422) cannot hide a missing authorization check.
GET_ROUTES = [
    "/datasets/{dataset_id}/metrics/recall_at_5",
    "/datasets/{dataset_id}/comparisons",
    "/datasets/{dataset_id}/evaluations/stats",
    "/datasets/{dataset_id}/regressions",
    "/datasets/{dataset_id}/regressions/summary",
    "/datasets/{dataset_id}/sets",
    "/datasets/{dataset_id}/versions",
    "/datasets/{dataset_id}/prompts/comparisons",
    "/datasets/{dataset_id}/rerankers/comparisons",
    "/datasets/{dataset_id}/retrievers/comparisons",
    "/jobs/{job_id}/comparison",
]
WRITE_ROUTES = [
    ("POST", "/datasets/{dataset_id}/questions", {"question": "attacker-question", "expected_answer": "attacker-answer"}),
    ("POST", "/datasets/{dataset_id}/questions/assign-split", {}),
    ("POST", "/datasets/{dataset_id}/compare", {}),
    ("POST", "/datasets/{dataset_id}/regressions/detect", {}),
    ("POST", "/datasets/{dataset_id}/sets", {"name": "attacker-set"}),
    ("POST", "/datasets/{dataset_id}/versions", {"name": "attacker-version"}),
    ("POST", "/datasets/{dataset_id}/versions/rollback", {}),
    ("POST", "/datasets/{dataset_id}/prompts/compare", {}),
    ("POST", "/datasets/{dataset_id}/rerankers/compare", {}),
    ("POST", "/datasets/{dataset_id}/retrievers/compare", {}),
]


async def test_the_remaining_eval_lab_routes_refuse_another_organization(client, db_session, monkeypatch):
    (owner, org_a, _), (attacker, _, _) = await make_tenants(client, db_session, monkeypatch, "evalext")
    dataset = EvaluationDataset(organization_id=org_a, name="private-dataset")
    db_session.add(dataset)
    await db_session.flush()
    question = EvaluationQuestion(dataset_id=dataset.id, question="private-question", expected_answer="private-answer")
    job = EvaluationJob(dataset_id=dataset.id, status="completed", total_questions=1)
    db_session.add_all([question, job])
    await db_session.flush()
    result = EvaluationResult(
        question_id=question.id, evaluation_job_id=job.id, model_config_json={}, retrieved_documents=[], retrieved_chunks=[],
        actual_answer="private-output", metrics={}, latency_ms=1,
    )
    failure = EvaluationFailure(evaluation_job_id=job.id, question_id=question.id, category="retrieval", error="private-failure")
    db_session.add_all([result, failure])
    await db_session.commit()
    ids = {"dataset_id": dataset.id, "job_id": job.id}
    baseline = await snapshot(db_session, dataset, question, job, result, failure)
    counts_before = [await db_session.scalar(select(func.count()).select_from(model)) for model in (EvaluationDataset, EvaluationQuestion, EvaluationJob)]

    schedule, provider = Mock(), AsyncMock()
    monkeypatch.setattr("api.routers.evaluation_jobs.schedule_evaluation_job_processing", schedule)
    monkeypatch.setattr("api.routers.evaluation_results.run_evaluation", provider)

    violations: list[str] = []
    for template in GET_ROUTES:
        path = template.format(**ids)
        owner_answer = await client.get(path, headers=owner)
        print(f"owner GET {path} -> {owner_answer.status_code}")
        assert owner_answer.status_code < 500, f"control failed for the owner: GET {path} -> {owner_answer.status_code}"
        await denied(client, "GET", path, attacker, violations)
    for method, template, body in WRITE_ROUTES:
        await denied(client, method, template.format(**ids), attacker, violations, json=body)

    assert await snapshot(db_session, dataset, question, job, result, failure) == baseline
    counts_after = [await db_session.scalar(select(func.count()).select_from(model)) for model in (EvaluationDataset, EvaluationQuestion, EvaluationJob)]
    assert counts_after == counts_before, "a refused request must not create or delete any evaluation row"
    schedule.assert_not_called()
    provider.assert_not_called()
    assert not violations, "\n".join(violations)

    # Control, after the attacker checks: the same write routes are NOT "not found" for the owner, so the refusals above came from authorization.
    for method, template, body in WRITE_ROUTES:
        path = template.format(**ids)
        owner_answer = await client.request(method, path, headers=owner, json=body)
        print(f"owner {method} {path} -> {owner_answer.status_code}")
        assert owner_answer.status_code not in (404, 405) and owner_answer.status_code < 500, f"control failed for the owner: {method} {path} -> {owner_answer.status_code}"

"""Partie 7.3.3 -- regression detection endpoints. Fast SQLite suite."""

import uuid

from sqlalchemy import select

from api.models.evaluation import EvaluationJob, EvaluationResult
from api.models.user import User


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _make_org_dataset_and_question(client, db_session, register_payload, name):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_id = (await client.post("/organizations", json={"name": name}, headers=_auth_header(owner_token))).json()["id"]
    dataset = (await client.post(f"/organizations/{org_id}/datasets", json={"name": "D"}, headers=_auth_header(owner_token))).json()
    question = (await client.post(f"/datasets/{dataset['id']}/questions", json={"question": "Q?"}, headers=_auth_header(owner_token))).json()
    return owner_token, dataset, question


async def _make_job_with_results(db_session, dataset_id, question_id, value):
    job = EvaluationJob(dataset_id=uuid.UUID(dataset_id), status="completed", total_questions=10, completed_questions=10)
    db_session.add(job)
    await db_session.flush()
    result_ids = []
    for _ in range(10):
        result = EvaluationResult(
            question_id=uuid.UUID(question_id), model_config_json={}, retrieved_documents=[], retrieved_chunks=[],
            actual_answer="a", metrics={"faithfulness": value}, latency_ms=1, evaluation_job_id=job.id,
        )
        db_session.add(result)
        await db_session.flush()
        result_ids.append(str(result.id))
    job.results = {"result_ids": result_ids}
    await db_session.commit()
    return job


async def test_detect_regressions_endpoint_works(client, db_session, register_payload):
    """Validation criterion: la détection de régression fonctionne."""
    owner_token, dataset, question = await _make_org_dataset_and_question(client, db_session, register_payload, "Regression Detect Endpoint Org")
    previous_job = await _make_job_with_results(db_session, dataset["id"], question["id"], 0.9)
    current_job = await _make_job_with_results(db_session, dataset["id"], question["id"], 0.3)

    response = await client.post(
        f"/datasets/{dataset['id']}/regressions/detect",
        json={"job_id": str(current_job.id), "previous_job_id": str(previous_job.id)}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 201
    assert any(d["metric"] == "faithfulness" for d in response.json())


async def test_get_regression_summary_endpoint_works(client, db_session, register_payload):
    owner_token, dataset, question = await _make_org_dataset_and_question(client, db_session, register_payload, "Regression Summary Endpoint Org")
    previous_job = await _make_job_with_results(db_session, dataset["id"], question["id"], 0.9)
    current_job = await _make_job_with_results(db_session, dataset["id"], question["id"], 0.3)
    await client.post(
        f"/datasets/{dataset['id']}/regressions/detect",
        json={"job_id": str(current_job.id), "previous_job_id": str(previous_job.id)}, headers=_auth_header(owner_token),
    )

    response = await client.get(f"/datasets/{dataset['id']}/regressions/summary", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["total"] >= 1


async def test_resolve_regression_endpoint_works(client, db_session, register_payload):
    """Validation criterion: la résolution fonctionne."""
    owner_token, dataset, question = await _make_org_dataset_and_question(client, db_session, register_payload, "Regression Resolve Endpoint Org")
    previous_job = await _make_job_with_results(db_session, dataset["id"], question["id"], 0.9)
    current_job = await _make_job_with_results(db_session, dataset["id"], question["id"], 0.3)
    detections = (await client.post(
        f"/datasets/{dataset['id']}/regressions/detect",
        json={"job_id": str(current_job.id), "previous_job_id": str(previous_job.id)}, headers=_auth_header(owner_token),
    )).json()

    response = await client.post(f"/regressions/{detections[0]['id']}/resolve", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["resolved_at"] is not None


async def test_get_regressions_endpoint_respects_permissions(client, db_session, register_payload):
    """Validation criterion: les permissions sont respectées."""
    owner_token, dataset, _question = await _make_org_dataset_and_question(client, db_session, register_payload, "Regression Perms Org")
    other_token, _other = await _register(client, db_session, "non-admin-regression@example.com")

    response = await client.get(f"/datasets/{dataset['id']}/regressions", headers=_auth_header(other_token))
    assert response.status_code == 404

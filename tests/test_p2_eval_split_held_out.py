"""Spec 7.1.7 -- tuning / held-out split of an Eval Lab dataset. Fast SQLite suite."""

import uuid

from sqlalchemy import select

from api.models.evaluation import EvaluationJob, EvaluationQuestion
from api.models.user import User
from api.services.evaluation_jobs import _filter_by_split


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _setup(client, db_session, register_payload, n_questions=40):
    token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    org_id = (await client.post("/organizations", json={"name": "Split Org"}, headers=_auth_header(token))).json()["id"]
    dataset = (await client.post(f"/organizations/{org_id}/datasets", json={"name": "ds"}, headers=_auth_header(token))).json()
    for i in range(n_questions):
        await client.post(f"/datasets/{dataset['id']}/questions", json={"question": f"Question {i}?", "expected_answer": str(i)}, headers=_auth_header(token))
    return token, org_id, dataset


async def test_questions_start_unassigned_and_accept_an_explicit_split(client, db_session, register_payload):
    token, _org, dataset = await _setup(client, db_session, register_payload, n_questions=0)
    plain = (await client.post(f"/datasets/{dataset['id']}/questions", json={"question": "a?"}, headers=_auth_header(token))).json()
    assert plain["split"] is None
    held = (await client.post(f"/datasets/{dataset['id']}/questions", json={"question": "b?", "split": "held_out"}, headers=_auth_header(token))).json()
    assert held["split"] == "held_out"
    bad = await client.post(f"/datasets/{dataset['id']}/questions", json={"question": "c?", "split": "test"}, headers=_auth_header(token))
    assert bad.status_code == 422
    moved = await client.patch(f"/questions/{plain['id']}", json={"split": "tuning"}, headers=_auth_header(token))
    assert moved.json()["split"] == "tuning"


async def test_assign_split_is_reproducible_and_roughly_proportional(client, db_session, register_payload):
    token, _org, dataset = await _setup(client, db_session, register_payload, n_questions=60)
    first = (await client.post(f"/datasets/{dataset['id']}/questions/assign-split", json={"held_out_ratio": 0.3, "seed": 7}, headers=_auth_header(token))).json()
    assert first["tuning"] + first["held_out"] == 60
    assert 8 <= first["held_out"] <= 30  # about 30 percent, with hash noise
    before = {q.id: q.split for q in (await db_session.scalars(select(EvaluationQuestion))).all()}
    again = (await client.post(f"/datasets/{dataset['id']}/questions/assign-split", json={"held_out_ratio": 0.3, "seed": 7, "overwrite": True}, headers=_auth_header(token))).json()
    assert again == first
    await db_session.rollback()
    after = {q.id: q.split for q in (await db_session.scalars(select(EvaluationQuestion))).all()}
    assert before == after


async def test_assign_split_does_not_overwrite_existing_assignments_by_default(client, db_session, register_payload):
    token, _org, dataset = await _setup(client, db_session, register_payload, n_questions=0)
    kept = (await client.post(f"/datasets/{dataset['id']}/questions", json={"question": "keep?", "split": "held_out"}, headers=_auth_header(token))).json()
    await client.post(f"/datasets/{dataset['id']}/questions/assign-split", json={"held_out_ratio": 0.01, "seed": 1}, headers=_auth_header(token))
    row = await db_session.scalar(select(EvaluationQuestion).where(EvaluationQuestion.id == uuid.UUID(kept["id"])))
    await db_session.refresh(row)
    assert row.split == "held_out"


async def test_only_dataset_admins_can_assign_a_split(client, db_session, register_payload):
    token, _org, dataset = await _setup(client, db_session, register_payload, n_questions=2)
    stranger = (await client.post("/auth/register", json={"email": "stranger-split@example.com", "password": "correct-horse-battery-staple", "accept_terms": True})).json()["access_token"]
    response = await client.post(f"/datasets/{dataset['id']}/questions/assign-split", json={}, headers=_auth_header(stranger))
    assert response.status_code in (403, 404)


async def test_a_job_with_a_split_only_evaluates_that_side(client, db_session, register_payload):
    q = lambda s: EvaluationQuestion(question="x", split=s)  # noqa: E731 -- tiny test helper
    questions = [q("held_out"), q("tuning"), q(None)]
    assert [x.split for x in _filter_by_split(questions, "held_out")] == ["held_out"]
    assert [x.split for x in _filter_by_split(questions, "tuning")] == ["tuning", None]  # unassigned counts as tuning
    assert _filter_by_split(questions, None) == questions


async def test_job_creation_stores_the_split(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr("api.routers.evaluation_jobs.schedule_evaluation_job_processing", lambda job_id: None)
    token, _org, dataset = await _setup(client, db_session, register_payload, n_questions=1)
    response = await client.post(f"/datasets/{dataset['id']}/evaluate", json={"split": "held_out"}, headers=_auth_header(token))
    assert response.status_code == 201
    assert response.json()["split"] == "held_out"
    job = await db_session.scalar(select(EvaluationJob))
    assert job.split == "held_out"
    assert User  # keep the import used by the shared fixtures' type checks

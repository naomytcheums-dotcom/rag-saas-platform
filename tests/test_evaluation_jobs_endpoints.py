"""Partie 7.3.1 -- automatic evaluation job endpoints. Fast SQLite
suite. schedule_evaluation_job_processing is mocked out (no real
Celery broker in tests) -- the endpoint tests exercise create/list/get/
cancel directly; run_evaluation_job's own real processing is already
covered by tests/test_evaluation_jobs.py."""

from unittest.mock import patch

from sqlalchemy import select

from api.models.user import User


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _make_org_and_dataset(client, db_session, register_payload, name):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_id = (await client.post("/organizations", json={"name": name}, headers=_auth_header(owner_token))).json()["id"]
    dataset = (await client.post(f"/organizations/{org_id}/datasets", json={"name": "D"}, headers=_auth_header(owner_token))).json()
    return owner_token, dataset


async def test_create_evaluation_job_endpoint_works(client, db_session, register_payload):
    """Validation criterion: la création de job fonctionne."""
    owner_token, dataset = await _make_org_and_dataset(client, db_session, register_payload, "Eval Job Endpoint Org")
    with patch("api.services.evaluation_jobs.schedule_evaluation_job_processing"):
        response = await client.post(f"/datasets/{dataset['id']}/evaluate", json={}, headers=_auth_header(owner_token))

    assert response.status_code == 201
    assert response.json()["status"] == "pending"


async def test_list_evaluation_jobs_endpoint_works(client, db_session, register_payload):
    owner_token, dataset = await _make_org_and_dataset(client, db_session, register_payload, "Eval Job List Endpoint Org")
    with patch("api.services.evaluation_jobs.schedule_evaluation_job_processing"):
        await client.post(f"/datasets/{dataset['id']}/evaluate", json={}, headers=_auth_header(owner_token))

    response = await client.get(f"/datasets/{dataset['id']}/jobs", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["total"] == 1


async def test_cancel_evaluation_job_endpoint_works(client, db_session, register_payload):
    """Validation criterion: l'annulation fonctionne."""
    owner_token, dataset = await _make_org_and_dataset(client, db_session, register_payload, "Eval Job Cancel Endpoint Org")
    with patch("api.services.evaluation_jobs.schedule_evaluation_job_processing"):
        job = (await client.post(f"/datasets/{dataset['id']}/evaluate", json={}, headers=_auth_header(owner_token))).json()

    response = await client.post(f"/jobs/{job['id']}/cancel", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


async def test_create_evaluation_job_endpoint_respects_permissions(client, db_session, register_payload):
    """Validation criterion: les permissions sont respectées."""
    owner_token, dataset = await _make_org_and_dataset(client, db_session, register_payload, "Eval Job Perms Org")
    other_token, _other = await _register(client, db_session, "non-admin-eval-job@example.com")

    response = await client.post(f"/datasets/{dataset['id']}/evaluate", json={}, headers=_auth_header(other_token))
    assert response.status_code == 404


async def test_get_evaluation_job_endpoint_respects_permissions(client, db_session, register_payload):
    """Validation criterion: les permissions sont respectées."""
    owner_token, dataset = await _make_org_and_dataset(client, db_session, register_payload, "Eval Job Get Perms Org")
    with patch("api.services.evaluation_jobs.schedule_evaluation_job_processing"):
        job = (await client.post(f"/datasets/{dataset['id']}/evaluate", json={}, headers=_auth_header(owner_token))).json()
    other_token, _other = await _register(client, db_session, "non-admin-eval-job-get@example.com")

    response = await client.get(f"/jobs/{job['id']}", headers=_auth_header(other_token))
    assert response.status_code == 404

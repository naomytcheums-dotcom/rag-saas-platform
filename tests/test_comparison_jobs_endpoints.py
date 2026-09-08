"""Partie 7.3.4/7.3.5/7.3.6/7.3.7 -- comparison job endpoints. Fast
SQLite suite. schedule_comparison_job_processing is mocked out (no
real Celery broker in tests)."""

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


async def test_create_model_comparison_endpoint_works(client, db_session, register_payload):
    """Validation criterion (7.3.4): la création de comparaison fonctionne."""
    owner_token, dataset = await _make_org_and_dataset(client, db_session, register_payload, "Model Comparison Endpoint Org")
    with patch("api.routers.comparison_jobs.schedule_comparison_job_processing"):
        response = await client.post(
            f"/datasets/{dataset['id']}/compare", json={"name": "C", "variants": [{"temperature": 0.1}]}, headers=_auth_header(owner_token),
        )
    assert response.status_code == 201
    assert response.json()["comparison_type"] == "model"


async def test_run_model_comparison_endpoint_works(client, db_session, register_payload):
    owner_token, dataset = await _make_org_and_dataset(client, db_session, register_payload, "Model Comparison Run Endpoint Org")
    # Patched where the router actually looks the name up (its own,
    # already-bound `from ... import` reference), not where it's
    # defined -- patching the service module's own attribute would
    # never reach the router's own separate, already-imported name.
    with patch("api.routers.comparison_jobs.schedule_comparison_job_processing") as mocked:
        job = (await client.post(
            f"/datasets/{dataset['id']}/compare", json={"name": "C", "variants": [{}]}, headers=_auth_header(owner_token),
        )).json()
        response = await client.post(f"/comparisons/{job['id']}/run", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert mocked.call_count == 2  # once on create, once on the explicit run


async def test_get_model_comparison_results_endpoint_works(client, db_session, register_payload):
    owner_token, dataset = await _make_org_and_dataset(client, db_session, register_payload, "Model Comparison Results Endpoint Org")
    with patch("api.routers.comparison_jobs.schedule_comparison_job_processing"):
        job = (await client.post(
            f"/datasets/{dataset['id']}/compare", json={"name": "C", "variants": [{}]}, headers=_auth_header(owner_token),
        )).json()
    response = await client.get(f"/comparisons/{job['id']}/results", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json() is None  # honestly not-yet-run


async def test_create_retriever_comparison_endpoint_works(client, db_session, register_payload):
    """Validation criterion (7.3.5)."""
    owner_token, dataset = await _make_org_and_dataset(client, db_session, register_payload, "Retriever Comparison Endpoint Org")
    with patch("api.routers.comparison_jobs.schedule_comparison_job_processing"):
        response = await client.post(
            f"/datasets/{dataset['id']}/retrievers/compare", json={"name": "R", "variants": ["hybrid", "vector_only"]},
            headers=_auth_header(owner_token),
        )
    assert response.status_code == 201
    assert response.json()["comparison_type"] == "retriever"

    listing = await client.get(f"/datasets/{dataset['id']}/retrievers/comparisons", headers=_auth_header(owner_token))
    assert listing.json()["total"] == 1


async def test_create_reranker_comparison_endpoint_works(client, db_session, register_payload):
    """Validation criterion (7.3.6)."""
    owner_token, dataset = await _make_org_and_dataset(client, db_session, register_payload, "Reranker Comparison Endpoint Org")
    with patch("api.routers.comparison_jobs.schedule_comparison_job_processing"):
        response = await client.post(
            f"/datasets/{dataset['id']}/rerankers/compare", json={"name": "RR", "variants": ["cross-encoder/ms-marco-MiniLM-L-6-v2"]},
            headers=_auth_header(owner_token),
        )
    assert response.status_code == 201
    comparison_id = response.json()["id"]

    get_response = await client.get(f"/reranker-comparisons/{comparison_id}", headers=_auth_header(owner_token))
    assert get_response.status_code == 200


async def test_create_prompt_comparison_endpoint_works(client, db_session, register_payload):
    """Validation criterion (7.3.7)."""
    owner_token, dataset = await _make_org_and_dataset(client, db_session, register_payload, "Prompt Comparison Endpoint Org")
    with patch("api.routers.comparison_jobs.schedule_comparison_job_processing"):
        response = await client.post(
            f"/datasets/{dataset['id']}/prompts/compare", json={"name": "P", "variants": ["Be terse.", "Be thorough."]},
            headers=_auth_header(owner_token),
        )
    assert response.status_code == 201
    assert response.json()["comparison_type"] == "prompt"


async def test_create_model_comparison_endpoint_respects_permissions(client, db_session, register_payload):
    """Validation criterion: les permissions sont respectées."""
    owner_token, dataset = await _make_org_and_dataset(client, db_session, register_payload, "Comparison Perms Org")
    other_token, _other = await _register(client, db_session, "non-admin-comparison-job@example.com")

    response = await client.post(
        f"/datasets/{dataset['id']}/compare", json={"name": "C", "variants": [{}]}, headers=_auth_header(other_token),
    )
    assert response.status_code == 404


async def test_get_model_comparison_endpoint_respects_permissions(client, db_session, register_payload):
    """Validation criterion: les permissions sont respectées."""
    owner_token, dataset = await _make_org_and_dataset(client, db_session, register_payload, "Comparison Get Perms Org")
    with patch("api.routers.comparison_jobs.schedule_comparison_job_processing"):
        job = (await client.post(
            f"/datasets/{dataset['id']}/compare", json={"name": "C", "variants": [{}]}, headers=_auth_header(owner_token),
        )).json()
    other_token, _other = await _register(client, db_session, "non-admin-comparison-job-get@example.com")

    response = await client.get(f"/comparisons/{job['id']}", headers=_auth_header(other_token))
    assert response.status_code == 404

"""Partie 7.1.6 -- benchmark version endpoints. Fast SQLite suite."""

import uuid

from sqlalchemy import select

from api.models.user import User


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _make_dataset_with_a_question(client, db_session, register_payload, name):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_response = await client.post("/organizations", json={"name": name}, headers=_auth_header(owner_token))
    org_id = org_response.json()["id"]
    dataset_response = await client.post(f"/organizations/{org_id}/datasets", json={"name": "D"}, headers=_auth_header(owner_token))
    dataset_id = dataset_response.json()["id"]
    await client.post(f"/datasets/{dataset_id}/questions", json={"question": "Q1?"}, headers=_auth_header(owner_token))
    return owner_token, dataset_id


async def test_create_benchmark_version_endpoint_works(client, db_session, register_payload):
    """Validation criterion: la création de version fonctionne."""
    owner_token, dataset_id = await _make_dataset_with_a_question(client, db_session, register_payload, "Version Create Org")
    response = await client.post(f"/datasets/{dataset_id}/versions", json={"description": "v1"}, headers=_auth_header(owner_token))
    assert response.status_code == 201
    assert response.json()["version_number"] == 1


async def test_compare_benchmark_versions_endpoint_works(client, db_session, register_payload):
    """Validation criterion: la comparaison de versions fonctionne."""
    owner_token, dataset_id = await _make_dataset_with_a_question(client, db_session, register_payload, "Version Compare Org")
    v1 = (await client.post(f"/datasets/{dataset_id}/versions", json={}, headers=_auth_header(owner_token))).json()
    await client.post(f"/datasets/{dataset_id}/questions", json={"question": "Q2?"}, headers=_auth_header(owner_token))
    v2 = (await client.post(f"/datasets/{dataset_id}/versions", json={}, headers=_auth_header(owner_token))).json()

    response = await client.post(f"/versions/{v1['id']}/compare/{v2['id']}", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["questions_added"] == 1


async def test_rollback_endpoint_works(client, db_session, register_payload):
    """Validation criterion: le rollback fonctionne."""
    owner_token, dataset_id = await _make_dataset_with_a_question(client, db_session, register_payload, "Version Rollback Org")
    v1 = (await client.post(f"/datasets/{dataset_id}/versions", json={}, headers=_auth_header(owner_token))).json()
    await client.post(f"/datasets/{dataset_id}/questions", json={"question": "Extra?"}, headers=_auth_header(owner_token))

    response = await client.post(
        f"/datasets/{dataset_id}/versions/rollback", json={"version_number": v1["version_number"]}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 200

    questions = await client.get(f"/datasets/{dataset_id}/questions", headers=_auth_header(owner_token))
    assert questions.json()["total"] == 1


async def test_non_admin_cannot_manage_versions(client, db_session, register_payload):
    """Validation criterion: les permissions sont respectées."""
    owner_token, dataset_id = await _make_dataset_with_a_question(client, db_session, register_payload, "Version Permission Org")
    v1 = (await client.post(f"/datasets/{dataset_id}/versions", json={}, headers=_auth_header(owner_token))).json()

    other_token, other = await _register(client, db_session, "non-admin-version@example.com")
    response = await client.get(f"/versions/{v1['id']}", headers=_auth_header(other_token))
    assert response.status_code == 404

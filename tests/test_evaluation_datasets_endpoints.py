"""Partie 7.1.1 -- dataset manager endpoints. Fast SQLite suite."""

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


async def _make_org_and_dataset(client, db_session, register_payload, name="Dataset Endpoint Org"):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_response = await client.post("/organizations", json={"name": name}, headers=_auth_header(owner_token))
    org_id = org_response.json()["id"]
    dataset_response = await client.post(
        f"/organizations/{org_id}/datasets", json={"name": "My Dataset", "description": "desc"}, headers=_auth_header(owner_token),
    )
    return owner_token, org_id, dataset_response.json()


async def test_create_dataset_endpoint_works(client, db_session, register_payload):
    """Validation criterion: la création de dataset fonctionne."""
    owner_token, org_id, dataset = await _make_org_and_dataset(client, db_session, register_payload)
    assert dataset["name"] == "My Dataset"
    assert dataset["version"] == 1


async def test_list_datasets_endpoint_returns_real_org_datasets(client, db_session, register_payload):
    owner_token, org_id, dataset = await _make_org_and_dataset(client, db_session, register_payload, "List Org")
    response = await client.get(f"/organizations/{org_id}/datasets", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["total"] == 1


async def test_non_admin_cannot_create_a_dataset(client, db_session, register_payload):
    """Validation criterion: les permissions sont respectées."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_response = await client.post("/organizations", json={"name": "Non Admin Org"}, headers=_auth_header(owner_token))
    org_id = org_response.json()["id"]

    other_token, other = await _register(client, db_session, "non-admin-dataset@example.com")
    response = await client.post(f"/organizations/{org_id}/datasets", json={"name": "x"}, headers=_auth_header(other_token))
    assert response.status_code == 404


async def test_add_question_endpoint_works(client, db_session, register_payload):
    """Validation criterion: l'ajout de questions fonctionne."""
    owner_token, org_id, dataset = await _make_org_and_dataset(client, db_session, register_payload, "Question Endpoint Org")
    response = await client.post(
        f"/datasets/{dataset['id']}/questions", json={"question": "What is 2+2?", "expected_answer": "4"},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 201
    assert response.json()["question"] == "What is 2+2?"


async def test_get_questions_endpoint_lists_real_questions(client, db_session, register_payload):
    owner_token, org_id, dataset = await _make_org_and_dataset(client, db_session, register_payload, "Question List Endpoint Org")
    await client.post(f"/datasets/{dataset['id']}/questions", json={"question": "Q1?"}, headers=_auth_header(owner_token))
    response = await client.get(f"/datasets/{dataset['id']}/questions", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["total"] == 1


async def test_import_questions_endpoint_accepts_a_real_uploaded_file(client, db_session, register_payload):
    """Validation criterion: l'import/export fonctionne."""
    owner_token, org_id, dataset = await _make_org_and_dataset(client, db_session, register_payload, "Import Endpoint Org")
    content = b'[{"question": "Imported question?"}]'
    response = await client.post(
        f"/datasets/{dataset['id']}/questions/import?format=json",
        files={"file": ("questions.json", content, "application/json")},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    assert response.json()["imported"] == 1


async def test_export_questions_endpoint_returns_real_json(client, db_session, register_payload):
    owner_token, org_id, dataset = await _make_org_and_dataset(client, db_session, register_payload, "Export Endpoint Org")
    await client.post(f"/datasets/{dataset['id']}/questions", json={"question": "Q1?"}, headers=_auth_header(owner_token))
    response = await client.get(f"/datasets/{dataset['id']}/questions/export?format=json", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert b"Q1?" in response.content


async def test_delete_dataset_endpoint_works(client, db_session, register_payload):
    owner_token, org_id, dataset = await _make_org_and_dataset(client, db_session, register_payload, "Delete Endpoint Org")
    response = await client.delete(f"/datasets/{dataset['id']}", headers=_auth_header(owner_token))
    assert response.status_code == 204
    follow_up = await client.get(f"/datasets/{dataset['id']}", headers=_auth_header(owner_token))
    assert follow_up.status_code == 404

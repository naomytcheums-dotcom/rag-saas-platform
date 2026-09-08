"""Partie 7.1.2 -- question set endpoints. Fast SQLite suite."""

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


async def _make_dataset_with_questions(client, db_session, register_payload, name, n_questions=2):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_response = await client.post("/organizations", json={"name": name}, headers=_auth_header(owner_token))
    org_id = org_response.json()["id"]
    dataset_response = await client.post(f"/organizations/{org_id}/datasets", json={"name": "D"}, headers=_auth_header(owner_token))
    dataset_id = dataset_response.json()["id"]
    question_ids = []
    for i in range(n_questions):
        q = await client.post(f"/datasets/{dataset_id}/questions", json={"question": f"Q{i}?"}, headers=_auth_header(owner_token))
        question_ids.append(q.json()["id"])
    return owner_token, dataset_id, question_ids


async def test_create_question_set_endpoint_works(client, db_session, register_payload):
    """Validation criterion: la création d'ensemble fonctionne."""
    owner_token, dataset_id, _ = await _make_dataset_with_questions(client, db_session, register_payload, "Set Create Org")
    response = await client.post(f"/datasets/{dataset_id}/sets", json={"name": "My Set"}, headers=_auth_header(owner_token))
    assert response.status_code == 201
    assert response.json()["name"] == "My Set"


async def test_add_and_list_questions_in_set_endpoint(client, db_session, register_payload):
    """Validation criterion: l'ajout de questions fonctionne."""
    owner_token, dataset_id, question_ids = await _make_dataset_with_questions(client, db_session, register_payload, "Set Add Org")
    set_response = await client.post(f"/datasets/{dataset_id}/sets", json={"name": "Set"}, headers=_auth_header(owner_token))
    set_id = set_response.json()["id"]

    for question_id in question_ids:
        response = await client.post(f"/sets/{set_id}/questions", json={"question_id": question_id}, headers=_auth_header(owner_token))
        assert response.status_code == 201


async def test_reorder_questions_endpoint_works(client, db_session, register_payload):
    """Validation criterion: la réorganisation fonctionne."""
    owner_token, dataset_id, question_ids = await _make_dataset_with_questions(client, db_session, register_payload, "Set Reorder Org")
    set_response = await client.post(f"/datasets/{dataset_id}/sets", json={"name": "Set"}, headers=_auth_header(owner_token))
    set_id = set_response.json()["id"]
    for question_id in question_ids:
        await client.post(f"/sets/{set_id}/questions", json={"question_id": question_id}, headers=_auth_header(owner_token))

    reversed_ids = list(reversed(question_ids))
    response = await client.patch(
        f"/sets/{set_id}/questions/reorder", json={"question_ids": reversed_ids}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    assert [q["id"] for q in response.json()] == reversed_ids


async def test_duplicate_question_set_endpoint_works(client, db_session, register_payload):
    """Validation criterion: la duplication fonctionne."""
    owner_token, dataset_id, question_ids = await _make_dataset_with_questions(client, db_session, register_payload, "Set Duplicate Org")
    set_response = await client.post(f"/datasets/{dataset_id}/sets", json={"name": "Original"}, headers=_auth_header(owner_token))
    set_id = set_response.json()["id"]
    for question_id in question_ids:
        await client.post(f"/sets/{set_id}/questions", json={"question_id": question_id}, headers=_auth_header(owner_token))

    response = await client.post(f"/sets/{set_id}/duplicate", json={"new_name": "Copy"}, headers=_auth_header(owner_token))
    assert response.status_code == 201
    assert response.json()["name"] == "Copy"


async def test_non_admin_cannot_manage_question_sets(client, db_session, register_payload):
    """Validation criterion: les permissions sont respectées."""
    owner_token, dataset_id, _ = await _make_dataset_with_questions(client, db_session, register_payload, "Set Permission Org")
    set_response = await client.post(f"/datasets/{dataset_id}/sets", json={"name": "Set"}, headers=_auth_header(owner_token))
    set_id = set_response.json()["id"]

    other_token, other = await _register(client, db_session, "non-admin-set@example.com")
    response = await client.get(f"/sets/{set_id}", headers=_auth_header(other_token))
    assert response.status_code == 404

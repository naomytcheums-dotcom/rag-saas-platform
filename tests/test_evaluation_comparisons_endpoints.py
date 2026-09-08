"""Partie 7.3 -- multi-model comparison and A/B-test endpoints. Fast SQLite suite."""

from unittest.mock import AsyncMock

import litellm
from litellm.types.utils import Choices, Message, ModelResponse
from sqlalchemy import select

from api.config import settings
from api.models.user import User


def _real_response(text: str) -> ModelResponse:
    message = Message(content=text, role="assistant")
    choice = Choices(message=message, index=0, finish_reason="stop")
    return ModelResponse(choices=[choice])


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _make_org_dataset_set_and_questions(client, db_session, register_payload, name, n_questions=2):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_id = (await client.post("/organizations", json={"name": name}, headers=_auth_header(owner_token))).json()["id"]
    dataset_id = (await client.post(f"/organizations/{org_id}/datasets", json={"name": "D"}, headers=_auth_header(owner_token))).json()["id"]
    set_id = (await client.post(f"/datasets/{dataset_id}/sets", json={"name": "S"}, headers=_auth_header(owner_token))).json()["id"]
    for i in range(n_questions):
        question_id = (await client.post(f"/datasets/{dataset_id}/questions", json={"question": f"Q{i}?"}, headers=_auth_header(owner_token))).json()["id"]
        await client.post(f"/sets/{set_id}/questions", json={"question_id": question_id}, headers=_auth_header(owner_token))
    return owner_token, set_id


async def test_run_multi_model_comparison_endpoint_works(monkeypatch, client, db_session, register_payload):
    """Validation criterion: comparaisons multi-modèles fonctionnent."""
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr("api.services.evaluation_results.search_with_context", AsyncMock(return_value=[]))
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("An answer.")))

    owner_token, set_id = await _make_org_dataset_set_and_questions(client, db_session, register_payload, "Comparison Endpoint Org")
    response = await client.post(
        f"/sets/{set_id}/compare", json={"model_configs": [{"temperature": 0.1}, {"temperature": 0.9}]}, headers=_auth_header(owner_token),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["sample_size"] == 2
    assert len(body["configs"]) == 2


async def test_run_ab_test_endpoint_works(monkeypatch, client, db_session, register_payload):
    """Validation criterion: A/B testing fonctionne."""
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr("api.services.evaluation_results.search_with_context", AsyncMock(return_value=[]))
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("An answer.")))

    owner_token, set_id = await _make_org_dataset_set_and_questions(client, db_session, register_payload, "AB Test Endpoint Org")
    response = await client.post(
        f"/sets/{set_id}/ab-test", json={"model_config_a": {"temperature": 0.1}, "model_config_b": {"temperature": 0.9}},
        headers=_auth_header(owner_token),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["sample_size"] == 2
    assert "p_value" in body


async def test_run_multi_model_comparison_endpoint_respects_permissions(client, db_session, register_payload):
    """Validation criterion: les permissions sont respectées."""
    owner_token, set_id = await _make_org_dataset_set_and_questions(client, db_session, register_payload, "Comparison Perms Org")
    other_token, _other = await _register(client, db_session, "non-admin-comparison@example.com")

    response = await client.post(f"/sets/{set_id}/compare", json={"model_configs": [{}]}, headers=_auth_header(other_token))
    assert response.status_code == 404


async def test_run_ab_test_endpoint_respects_permissions(client, db_session, register_payload):
    """Validation criterion: les permissions sont respectées."""
    owner_token, set_id = await _make_org_dataset_set_and_questions(client, db_session, register_payload, "AB Test Perms Org")
    other_token, _other = await _register(client, db_session, "non-admin-ab-test@example.com")

    response = await client.post(
        f"/sets/{set_id}/ab-test", json={"model_config_a": {}, "model_config_b": {}}, headers=_auth_header(other_token),
    )
    assert response.status_code == 404

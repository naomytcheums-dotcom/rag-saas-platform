"""Partie 7.2.1 -- evaluation-run endpoints. Fast SQLite suite."""

import uuid
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


async def _make_org_dataset_and_question(client, db_session, register_payload, name="Eval Results Endpoint Org"):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_id = (await client.post("/organizations", json={"name": name}, headers=_auth_header(owner_token))).json()["id"]
    dataset = (await client.post(
        f"/organizations/{org_id}/datasets", json={"name": "D", "description": "d"}, headers=_auth_header(owner_token),
    )).json()
    question = (await client.post(
        f"/datasets/{dataset['id']}/questions", json={"question": "Why is the sky blue?"}, headers=_auth_header(owner_token),
    )).json()
    return owner_token, org_id, dataset, question


async def test_run_evaluation_endpoint_works(monkeypatch, client, db_session, register_payload):
    """Validation criterion (7.2.1): les résultats d'évaluation sont stockés."""
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr("api.services.evaluation_results.search_with_context", AsyncMock(return_value=[]))
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("An answer.")))

    owner_token, _org_id, _dataset, question = await _make_org_dataset_and_question(client, db_session, register_payload)
    response = await client.post(f"/questions/{question['id']}/run", json={}, headers=_auth_header(owner_token))

    assert response.status_code == 201
    body = response.json()
    assert body["actual_answer"] == "An answer."
    assert "recall_at_1" in body["metrics"]


async def test_get_evaluation_results_endpoint_lists_real_results(monkeypatch, client, db_session, register_payload):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr("api.services.evaluation_results.search_with_context", AsyncMock(return_value=[]))
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("An answer.")))

    owner_token, _org_id, _dataset, question = await _make_org_dataset_and_question(client, db_session, register_payload, "Eval Results List Org")
    await client.post(f"/questions/{question['id']}/run", json={}, headers=_auth_header(owner_token))

    response = await client.get(f"/questions/{question['id']}/results", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["total"] == 1


async def test_get_metrics_summary_endpoint_works(monkeypatch, client, db_session, register_payload):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr("api.services.evaluation_results.search_with_context", AsyncMock(return_value=[]))
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("An answer.")))

    owner_token, _org_id, dataset, question = await _make_org_dataset_and_question(client, db_session, register_payload, "Eval Metrics Endpoint Org")
    await client.post(f"/questions/{question['id']}/run", json={}, headers=_auth_header(owner_token))

    response = await client.get(f"/datasets/{dataset['id']}/metrics/answer_relevance", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["count"] == 1


async def test_run_evaluation_endpoint_respects_permissions(client, db_session, register_payload):
    """Validation criterion: les permissions sont respectées."""
    owner_token, _org_id, _dataset, question = await _make_org_dataset_and_question(client, db_session, register_payload, "Eval Perms Org")
    other_token, _other = await _register(client, db_session, "non-admin-eval-results@example.com")

    response = await client.post(f"/questions/{question['id']}/run", json={}, headers=_auth_header(other_token))
    assert response.status_code == 404


async def test_get_evaluation_results_endpoint_respects_permissions(client, db_session, register_payload):
    """Validation criterion: les permissions sont respectées."""
    owner_token, _org_id, _dataset, question = await _make_org_dataset_and_question(client, db_session, register_payload, "Eval Perms Results Org")
    other_token, _other = await _register(client, db_session, "non-admin-eval-results-2@example.com")

    response = await client.get(f"/questions/{question['id']}/results", headers=_auth_header(other_token))
    assert response.status_code == 404

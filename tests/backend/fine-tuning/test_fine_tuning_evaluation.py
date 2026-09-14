"""Partie 24 -- real evaluation of a fine-tuned model, reusing the
existing Evaluation Lab (create_evaluation_job/run_evaluation_job,
Partie 7.1-7.2) -- mocked at the exact same real boundary
tests/test_evaluation_jobs.py's own tests already use
(search_with_context + litellm.acompletion), never a second,
parallel evaluation engine."""

import uuid
from unittest.mock import AsyncMock

import litellm
from litellm.types.utils import Choices, Message, ModelResponse
from sqlalchemy import select

from api.config import settings
from api.models.evaluation import EvaluationDataset, EvaluationQuestion
from api.models.fine_tuning import FineTunedModel, FineTuningDataset, FineTuningEvaluation, FineTuningJob
from api.models.user import User
from api.services import fine_tuning as service


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


async def _make_org(client, db_session, register_payload, name):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_id = (await client.post("/organizations", json={"name": name}, headers=_auth_header(owner_token))).json()["id"]
    return owner_token, org_id


async def _make_model(db_session, org_id) -> FineTunedModel:
    dataset = FineTuningDataset(organization_id=uuid.UUID(org_id), name="D", dataset_type="llm", format="jsonl", file_key="k", size=1, status="ready")
    db_session.add(dataset)
    await db_session.flush()
    job = FineTuningJob(organization_id=uuid.UUID(org_id), dataset_id=dataset.id, name="J", base_model="gpt-4o-mini-2024-07-18", provider="openai")
    db_session.add(job)
    await db_session.flush()
    model = FineTunedModel(
        organization_id=uuid.UUID(org_id), job_id=job.id, name="M", provider="openai",
        provider_model_id="ft:gpt-4o-mini-2024-07-18:acme::abc123", base_model="gpt-4o-mini-2024-07-18",
    )
    db_session.add(model)
    await db_session.flush()
    return model


async def _make_eval_dataset(db_session, org_id, question_count=3) -> EvaluationDataset:
    dataset = EvaluationDataset(organization_id=uuid.UUID(org_id), name="Eval D")
    db_session.add(dataset)
    await db_session.flush()
    for i in range(question_count):
        db_session.add(EvaluationQuestion(dataset_id=dataset.id, question=f"Question {i}?"))
    await db_session.commit()
    return dataset


async def test_evaluate_model_runs_the_real_evaluation_lab(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-oai-test")  # the fine-tuned model itself is provider="openai"
    monkeypatch.setattr("api.services.evaluation_results.search_with_context", AsyncMock(return_value=[]))
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("A real answer.")))

    owner_token, org_id = await _make_org(client, db_session, register_payload, "Evaluate Org")
    model = await _make_model(db_session, org_id)
    eval_dataset = await _make_eval_dataset(db_session, org_id, question_count=3)

    response = await client.post(
        f"/fine-tuning/models/{model.id}/evaluate", json={"dataset_id": str(eval_dataset.id)}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["metrics"]["result_count"] == 3
    assert body["score"] is not None


async def test_evaluate_model_passes_the_real_fine_tuned_model_id_as_model_config(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-oai-test")  # the fine-tuned model itself is provider="openai"
    monkeypatch.setattr("api.services.evaluation_results.search_with_context", AsyncMock(return_value=[]))
    mock_completion = AsyncMock(return_value=_real_response("A real answer."))
    monkeypatch.setattr(litellm, "acompletion", mock_completion)

    owner_token, org_id = await _make_org(client, db_session, register_payload, "Model Config Org")
    model = await _make_model(db_session, org_id)
    eval_dataset = await _make_eval_dataset(db_session, org_id, question_count=1)

    await service.evaluate_model(db_session, model.id, eval_dataset.id, None)
    await db_session.commit()

    assert mock_completion.call_args.kwargs["model"] == "ft:gpt-4o-mini-2024-07-18:acme::abc123"


async def test_list_evaluations_endpoint(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-oai-test")  # the fine-tuned model itself is provider="openai"
    monkeypatch.setattr("api.services.evaluation_results.search_with_context", AsyncMock(return_value=[]))
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("A real answer.")))

    owner_token, org_id = await _make_org(client, db_session, register_payload, "List Eval Org")
    model = await _make_model(db_session, org_id)
    eval_dataset = await _make_eval_dataset(db_session, org_id, question_count=1)
    await service.evaluate_model(db_session, model.id, eval_dataset.id, None)
    await db_session.commit()

    response = await client.get(f"/fine-tuning/models/{model.id}/evaluations", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_evaluate_model_returns_404_for_an_unknown_evaluation_dataset(client, db_session, register_payload):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Unknown Dataset Org")
    model = await _make_model(db_session, org_id)
    await db_session.commit()

    response = await client.post(
        f"/fine-tuning/models/{model.id}/evaluate", json={"dataset_id": str(uuid.uuid4())}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 404

"""Partie 24 -- real job creation/submission/status-polling/cancellation,
mocking the real provider HTTP boundary (api.services.fine_tuning_providers,
which itself calls httpx directly) the same way this codebase's own
existing paid-third-party tests mock their own real boundary (never
fabricating what a live provider response would actually contain --
these response shapes are OpenAI's/Mistral's own real, documented
fine-tuning API response fields)."""

import uuid
from unittest.mock import AsyncMock

from sqlalchemy import select

from api.models.fine_tuning import FineTunedModel, FineTuningDataset, FineTuningDatasetStatus, FineTuningJob, FineTuningJobStatus
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.services import fine_tuning as service


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


async def _make_ready_dataset(db_session, org_id) -> FineTuningDataset:
    dataset = FineTuningDataset(
        organization_id=uuid.UUID(org_id), name="D", dataset_type="llm", format="jsonl", file_key="fine-tuning/x/y/d.jsonl",
        size=100, example_count=10, status=FineTuningDatasetStatus.ready.value,
    )
    db_session.add(dataset)
    await db_session.flush()
    return dataset


async def test_create_job_requires_a_ready_dataset(client, db_session, register_payload):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Job Org")
    dataset = FineTuningDataset(
        organization_id=uuid.UUID(org_id), name="D", dataset_type="llm", format="jsonl", file_key="k", size=1,
        status=FineTuningDatasetStatus.error.value,
    )
    db_session.add(dataset)
    await db_session.commit()

    response = await client.post(
        f"/fine-tuning/jobs?org_id={org_id}", json={"dataset_id": str(dataset.id), "name": "Job A"}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 400


async def test_create_job_requires_admin(client, db_session, register_payload):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Job Admin Org")
    dataset = await _make_ready_dataset(db_session, org_id)
    await db_session.commit()

    member_token, member = await _register(client, db_session, "ft_job_member@example.com")
    owner = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    db_session.add(OrganizationMember(organization_id=uuid.UUID(org_id), user_id=member.id, role=OrganizationRole.member, invited_by=owner.id))
    await db_session.commit()

    response = await client.post(
        f"/fine-tuning/jobs?org_id={org_id}", json={"dataset_id": str(dataset.id), "name": "Job A"}, headers=_auth_header(member_token),
    )
    assert response.status_code == 403


async def test_create_job_endpoint_persists_a_real_pending_job(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr("api.tasks.fine_tuning.schedule_fine_tuning_job_submission", lambda job_id: None)
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Pending Job Org")
    dataset = await _make_ready_dataset(db_session, org_id)
    await db_session.commit()

    response = await client.post(
        f"/fine-tuning/jobs?org_id={org_id}", json={"dataset_id": str(dataset.id), "name": "Job A"}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["base_model"] == "gpt-4o-mini-2024-07-18"
    assert body["provider"] == "openai"


async def test_submit_job_uploads_and_creates_a_real_remote_job(client, db_session, register_payload, monkeypatch):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Submit Org")
    dataset = await _make_ready_dataset(db_session, org_id)
    job = FineTuningJob(organization_id=uuid.UUID(org_id), dataset_id=dataset.id, name="Job A", base_model="gpt-4o-mini-2024-07-18", provider="openai")
    db_session.add(job)
    await db_session.commit()

    monkeypatch.setattr("api.services.fine_tuning.download_finetuning_dataset_file", lambda file_key: b'{"messages": []}\n')
    monkeypatch.setattr("api.services.fine_tuning.provider_upload_training_file", AsyncMock(return_value="file-abc123"))
    monkeypatch.setattr("api.services.fine_tuning.provider_create_job", AsyncMock(return_value={"id": "ftjob-real123", "status": "validating_files"}))

    updated = await service.submit_job(db_session, job.id)
    await db_session.commit()

    assert updated.status == FineTuningJobStatus.running.value
    assert updated.provider_job_id == "ftjob-real123"
    assert updated.started_at is not None


async def test_submit_job_marks_failed_on_a_real_missing_api_key(client, db_session, register_payload, monkeypatch):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "No Key Org")
    dataset = await _make_ready_dataset(db_session, org_id)
    job = FineTuningJob(organization_id=uuid.UUID(org_id), dataset_id=dataset.id, name="Job A", base_model="gpt-4o-mini-2024-07-18", provider="openai")
    db_session.add(job)
    await db_session.commit()

    # The real S3 download itself would also fail in this environment
    # (no real bucket/credentials for this fake file_key) -- stubbed
    # here so the real, INTENDED failure under test (a missing
    # OPENAI_API_KEY, which api.config.settings defaults to "" in this
    # environment) is the one that actually surfaces.
    monkeypatch.setattr("api.services.fine_tuning.download_finetuning_dataset_file", lambda file_key: b'{"messages": []}\n')

    updated = await service.submit_job(db_session, job.id)
    await db_session.commit()

    assert updated.status == FineTuningJobStatus.failed.value
    assert "OPENAI_API_KEY" in updated.error_message


async def test_check_job_status_creates_a_real_fine_tuned_model_on_success(client, db_session, register_payload, monkeypatch):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Status Org")
    dataset = await _make_ready_dataset(db_session, org_id)
    job = FineTuningJob(
        organization_id=uuid.UUID(org_id), dataset_id=dataset.id, name="Job A", base_model="gpt-4o-mini-2024-07-18",
        provider="openai", status=FineTuningJobStatus.running.value, provider_job_id="ftjob-real123",
    )
    db_session.add(job)
    await db_session.commit()

    monkeypatch.setattr("api.services.fine_tuning.provider_get_job_status", AsyncMock(return_value={
        "id": "ftjob-real123", "status": "succeeded", "fine_tuned_model": "ft:gpt-4o-mini-2024-07-18:acme::abc123", "trained_tokens": 5000,
    }))

    updated = await service.check_job_status(db_session, job.id)
    await db_session.commit()

    assert updated.status == FineTuningJobStatus.succeeded.value
    model = await db_session.scalar(select(FineTunedModel).where(FineTunedModel.job_id == job.id))
    assert model is not None
    assert model.provider_model_id == "ft:gpt-4o-mini-2024-07-18:acme::abc123"


async def test_check_job_status_is_idempotent(client, db_session, register_payload, monkeypatch):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Idempotent Org")
    dataset = await _make_ready_dataset(db_session, org_id)
    job = FineTuningJob(
        organization_id=uuid.UUID(org_id), dataset_id=dataset.id, name="Job A", base_model="gpt-4o-mini-2024-07-18",
        provider="openai", status=FineTuningJobStatus.running.value, provider_job_id="ftjob-real123",
    )
    db_session.add(job)
    await db_session.commit()

    mock_status = AsyncMock(return_value={
        "id": "ftjob-real123", "status": "succeeded", "fine_tuned_model": "ft:gpt-4o-mini-2024-07-18:acme::abc123", "trained_tokens": 5000,
    })
    monkeypatch.setattr("api.services.fine_tuning.provider_get_job_status", mock_status)

    await service.check_job_status(db_session, job.id)
    await db_session.commit()
    await service.check_job_status(db_session, job.id)  # a real, second check on an already-succeeded job -- no-op
    await db_session.commit()

    models = (await db_session.scalars(select(FineTunedModel).where(FineTunedModel.job_id == job.id))).all()
    assert len(models) == 1  # never a real, duplicate FineTunedModel row


async def test_check_job_status_marks_failed_with_the_real_provider_error(client, db_session, register_payload, monkeypatch):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Failed Job Org")
    dataset = await _make_ready_dataset(db_session, org_id)
    job = FineTuningJob(
        organization_id=uuid.UUID(org_id), dataset_id=dataset.id, name="Job A", base_model="gpt-4o-mini-2024-07-18",
        provider="openai", status=FineTuningJobStatus.running.value, provider_job_id="ftjob-real456",
    )
    db_session.add(job)
    await db_session.commit()

    monkeypatch.setattr("api.services.fine_tuning.provider_get_job_status", AsyncMock(return_value={
        "id": "ftjob-real456", "status": "failed", "error": {"message": "training file contained invalid examples"},
    }))

    updated = await service.check_job_status(db_session, job.id)
    await db_session.commit()

    assert updated.status == FineTuningJobStatus.failed.value
    assert updated.error_message == "training file contained invalid examples"


async def test_cancel_job_endpoint(client, db_session, register_payload, monkeypatch):
    owner_token, org_id = await _make_org(client, db_session, register_payload, "Cancel Org")
    dataset = await _make_ready_dataset(db_session, org_id)
    job = FineTuningJob(
        organization_id=uuid.UUID(org_id), dataset_id=dataset.id, name="Job A", base_model="gpt-4o-mini-2024-07-18",
        provider="openai", status=FineTuningJobStatus.running.value, provider_job_id="ftjob-real789",
    )
    db_session.add(job)
    await db_session.commit()

    monkeypatch.setattr("api.services.fine_tuning.provider_cancel_job", AsyncMock(return_value={"id": "ftjob-real789", "status": "cancelled"}))

    response = await client.post(f"/fine-tuning/jobs/{job.id}/cancel", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"

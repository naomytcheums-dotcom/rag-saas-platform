"""
Partie 2.2.16 -- tests for BatchJob/BatchJobItem CRUD, real per-item
dispatch/resilience/resumability, and its 5 routes.

The 5 real underlying functions each job_type dispatches to
(upload_document/reindex_document/soft_delete_document/
sync_external_source/replace_document) are already tested extensively
elsewhere -- mocked here at their own real call boundary (patched on
api.security.batch_jobs, the module that actually calls them -- this
codebase's own established "patch where it's used" lesson), since
these tests exist to prove THIS étape's own real orchestration, not
the underlying pipelines' own internals a second time.
"""

import base64
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from api.models.batch_job import BatchJob, BatchJobItem, BatchJobItemStatus, BatchJobStatus
from api.models.document import Document, DocumentStatus
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.security.batch_jobs import (
    cancel_batch_job,
    create_batch_job,
    get_batch_job_status,
    list_batch_job_items,
    process_batch_job,
)


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _create_org(client, access_token: str, name: str) -> dict:
    return (await client.post("/organizations", json={"name": name}, headers=_auth_header(access_token))).json()


async def _add_member(db_session, org_id, user_id, role: OrganizationRole, invited_by=None):
    db_session.add(OrganizationMember(organization_id=org_id, user_id=user_id, role=role, invited_by=invited_by))
    await db_session.commit()


async def _make_document(session, organization_id=None) -> Document:
    document = Document(
        organization_id=organization_id or uuid.uuid4(), name="a.pdf", file_key="k", file_size=1, file_type="application/pdf",
        status=DocumentStatus.completed.value,
    )
    session.add(document)
    await session.commit()
    return document


# ============================================================= CRUD =============================================================

async def test_create_batch_job_rejects_an_unsupported_type(db_session):
    with pytest.raises(ValueError, match="job_type"):
        await create_batch_job(db_session, uuid.uuid4(), "teleport", [{"document_id": "x"}], None, None)


async def test_create_batch_job_rejects_an_empty_item_list(db_session):
    with pytest.raises(ValueError, match="at least one"):
        await create_batch_job(db_session, uuid.uuid4(), "reindex", [], None, None)


async def test_create_batch_job_creates_one_item_per_real_input(db_session):
    """Validation criterion: la création d'un job fonctionne."""
    job = await create_batch_job(
        db_session, uuid.uuid4(), "reindex", [{"document_id": str(uuid.uuid4())}, {"document_id": str(uuid.uuid4())}], None, None,
    )
    assert job.total_items == 2
    assert job.status == BatchJobStatus.pending.value
    items = await list_batch_job_items(db_session, job.id)
    assert [item.sequence for item in items] == [0, 1]
    assert all(item.status == BatchJobItemStatus.pending.value for item in items)


async def test_get_batch_job_status_raises_for_a_nonexistent_job(db_session):
    with pytest.raises(ValueError, match="not a registered batch job"):
        await get_batch_job_status(db_session, uuid.uuid4())


# ========================================================== process_batch_job ===========================================================

async def test_process_batch_job_reindex_dispatches_to_the_real_pipeline(db_session):
    """Validation criterion: le traitement d'un job fonctionne."""
    document_id = uuid.uuid4()
    job = await create_batch_job(db_session, uuid.uuid4(), "reindex", [{"document_id": str(document_id)}], None, uuid.uuid4())

    with patch("api.security.batch_jobs.reindex_document", AsyncMock(return_value=DocumentStatus.completed.value)) as mock_reindex:
        result = await process_batch_job(db_session, job.id)

    assert result.status == BatchJobStatus.completed.value
    assert result.processed_items == 1
    assert result.failed_items == 0
    mock_reindex.assert_awaited_once_with(db_session, document_id, triggered_by=job.created_by)
    items = await list_batch_job_items(db_session, job.id)
    assert items[0].status == BatchJobItemStatus.completed.value
    assert items[0].item_id == document_id


async def test_process_batch_job_upload_decodes_real_base64_content(db_session):
    organization_id = uuid.uuid4()
    content = b"%PDF-1.4 real batch upload content"
    job = await create_batch_job(
        db_session, organization_id, "upload",
        [{"filename": "a.pdf", "content_b64": base64.b64encode(content).decode("ascii")}], None, None,
    )
    new_document = await _make_document(db_session, organization_id=organization_id)

    with patch("api.security.batch_jobs.upload_document", AsyncMock(return_value=(new_document, False))) as mock_upload:
        result = await process_batch_job(db_session, job.id)

    assert result.status == BatchJobStatus.completed.value
    mock_upload.assert_awaited_once_with(db_session, organization_id, None, None, "a.pdf", content)


async def test_process_batch_job_tolerates_a_real_failure_for_one_item(db_session):
    """Vision critique 2/3 -- un item qui échoue ne bloque pas les
    autres, et l'erreur est journalisée sur cet item précis."""
    good_id, bad_id = uuid.uuid4(), uuid.uuid4()
    job = await create_batch_job(
        db_session, uuid.uuid4(), "reindex", [{"document_id": str(good_id)}, {"document_id": str(bad_id)}], None, None,
    )

    async def _flaky(db, document_id, triggered_by=None):
        if document_id == bad_id:
            raise RuntimeError("real reindex failure")
        return DocumentStatus.completed.value

    with patch("api.security.batch_jobs.reindex_document", side_effect=_flaky):
        result = await process_batch_job(db_session, job.id)

    assert result.status == BatchJobStatus.completed.value  # the JOB itself still finished
    assert result.processed_items == 1
    assert result.failed_items == 1
    items = await list_batch_job_items(db_session, job.id)
    by_sequence = {item.sequence: item for item in items}
    assert by_sequence[0].status == BatchJobItemStatus.completed.value
    assert by_sequence[1].status == BatchJobItemStatus.failed.value
    assert by_sequence[1].error is not None


async def test_process_batch_job_records_a_real_catastrophic_failure(db_session):
    """Le job lui-même ne reste jamais bloqué à `processing`."""
    job = await create_batch_job(db_session, uuid.uuid4(), "reindex", [{"document_id": str(uuid.uuid4())}], None, None)
    job.config = None  # a real, malformed config -- .get("items") will blow up
    await db_session.commit()

    result = await process_batch_job(db_session, job.id)

    assert result.status == BatchJobStatus.failed.value
    assert result.error is not None
    assert result.completed_at is not None


async def test_process_batch_job_stops_at_a_real_cancellation(db_session):
    document_ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
    job = await create_batch_job(db_session, uuid.uuid4(), "reindex", [{"document_id": str(d)} for d in document_ids], None, None)

    call_count = 0

    async def _cancel_after_first(db, document_id, triggered_by=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            await cancel_batch_job(db, job.id)
        return DocumentStatus.completed.value

    with patch("api.security.batch_jobs.reindex_document", side_effect=_cancel_after_first):
        result = await process_batch_job(db_session, job.id)

    assert result.status == BatchJobStatus.cancelled.value
    items = await list_batch_job_items(db_session, job.id)
    statuses = [item.status for item in items]
    assert BatchJobItemStatus.pending.value in statuses  # at least one item never got processed


async def test_resuming_a_batch_job_only_retries_pending_items(db_session):
    """Robustesse -- reprendre un job interrompu ne retraite jamais un
    item déjà traité avec succès, seulement ceux encore en attente."""
    document_ids = [uuid.uuid4(), uuid.uuid4()]
    job = await create_batch_job(db_session, uuid.uuid4(), "reindex", [{"document_id": str(d)} for d in document_ids], None, None)

    call_count = 0

    async def _cancel_after_first(db, document_id, triggered_by=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            await cancel_batch_job(db, job.id)
        return DocumentStatus.completed.value

    with patch("api.security.batch_jobs.reindex_document", side_effect=_cancel_after_first):
        interrupted = await process_batch_job(db_session, job.id)
    assert interrupted.status == BatchJobStatus.cancelled.value

    with patch("api.security.batch_jobs.reindex_document", AsyncMock(return_value=DocumentStatus.completed.value)) as mock_reindex:
        resumed = await process_batch_job(db_session, job.id)

    assert resumed.status == BatchJobStatus.completed.value
    mock_reindex.assert_awaited_once()  # only the ONE real remaining pending item, not the first one again


async def test_cancel_batch_job_rejects_an_already_completed_job(db_session):
    job = await create_batch_job(db_session, uuid.uuid4(), "reindex", [{"document_id": str(uuid.uuid4())}], None, None)
    with patch("api.security.batch_jobs.reindex_document", AsyncMock(return_value=DocumentStatus.completed.value)):
        await process_batch_job(db_session, job.id)

    with pytest.raises(ValueError, match="already completed"):
        await cancel_batch_job(db_session, job.id)


# ============================================================ routes ============================================================

async def test_admin_can_create_and_the_job_gets_scheduled(client, db_session, register_payload, monkeypatch):
    """Validation criterion: la création d'un job fonctionne (via la
    route). Performance (vision critique 1) -- réellement planifié via
    Celery, pas exécuté en synchrone dans la requête."""
    scheduled_ids = []
    monkeypatch.setattr("api.security.batch_jobs.schedule_batch_job_processing", lambda job_id: scheduled_ids.append(job_id))
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(
        f"/organizations/{org['id']}/batch/jobs", headers=_auth_header(owner_token),
        json={"job_type": "reindex", "items": [{"document_id": str(uuid.uuid4())}]},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["total_items"] == 1
    assert len(scheduled_ids) == 1


async def test_create_batch_job_rejects_an_invalid_type_via_the_route(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(
        f"/organizations/{org['id']}/batch/jobs", headers=_auth_header(owner_token),
        json={"job_type": "teleport", "items": [{"x": "y"}]},
    )
    assert response.status_code == 400


async def test_member_cannot_create_a_batch_job(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    member_token, member = await _register(client, db_session, "batchmember@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.post(
        f"/organizations/{org['id']}/batch/jobs", headers=_auth_header(member_token),
        json={"job_type": "reindex", "items": [{"document_id": str(uuid.uuid4())}]},
    )
    assert response.status_code == 403


async def test_admin_can_list_batch_jobs(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr("api.security.batch_jobs.schedule_batch_job_processing", lambda job_id: None)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.post(
        f"/organizations/{org['id']}/batch/jobs", headers=_auth_header(owner_token),
        json={"job_type": "reindex", "items": [{"document_id": str(uuid.uuid4())}]},
    )

    response = await client.get(f"/organizations/{org['id']}/batch/jobs", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_admin_can_get_a_batch_job_status(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr("api.security.batch_jobs.schedule_batch_job_processing", lambda job_id: None)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(
        f"/organizations/{org['id']}/batch/jobs", headers=_auth_header(owner_token),
        json={"job_type": "reindex", "items": [{"document_id": str(uuid.uuid4())}]},
    )
    job_id = created.json()["id"]

    response = await client.get(f"/batch/jobs/{job_id}", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["id"] == job_id


async def test_batch_job_belonging_to_another_organization_returns_404(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr("api.security.batch_jobs.schedule_batch_job_processing", lambda job_id: None)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(
        f"/organizations/{org['id']}/batch/jobs", headers=_auth_header(owner_token),
        json={"job_type": "reindex", "items": [{"document_id": str(uuid.uuid4())}]},
    )
    job_id = created.json()["id"]
    outsider_token, outsider = await _register(client, db_session, "batchoutsider@example.com")

    response = await client.get(f"/batch/jobs/{job_id}", headers=_auth_header(outsider_token))
    assert response.status_code == 404


async def test_admin_can_cancel_a_batch_job(client, db_session, register_payload, monkeypatch):
    """Validation criterion: l'annulation d'un job fonctionne."""
    monkeypatch.setattr("api.security.batch_jobs.schedule_batch_job_processing", lambda job_id: None)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(
        f"/organizations/{org['id']}/batch/jobs", headers=_auth_header(owner_token),
        json={"job_type": "reindex", "items": [{"document_id": str(uuid.uuid4())}]},
    )
    job_id = created.json()["id"]

    response = await client.post(f"/batch/jobs/{job_id}/cancel", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


async def test_admin_can_list_batch_job_items(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr("api.security.batch_jobs.schedule_batch_job_processing", lambda job_id: None)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(
        f"/organizations/{org['id']}/batch/jobs", headers=_auth_header(owner_token),
        json={"job_type": "reindex", "items": [{"document_id": str(uuid.uuid4())}, {"document_id": str(uuid.uuid4())}]},
    )
    job_id = created.json()["id"]

    response = await client.get(f"/batch/jobs/{job_id}/items", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert len(response.json()) == 2


async def test_member_cannot_cancel_a_batch_job(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr("api.security.batch_jobs.schedule_batch_job_processing", lambda job_id: None)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(
        f"/organizations/{org['id']}/batch/jobs", headers=_auth_header(owner_token),
        json={"job_type": "reindex", "items": [{"document_id": str(uuid.uuid4())}]},
    )
    job_id = created.json()["id"]
    member_token, member = await _register(client, db_session, "batchcancelmember@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.post(f"/batch/jobs/{job_id}/cancel", headers=_auth_header(member_token))
    assert response.status_code == 403

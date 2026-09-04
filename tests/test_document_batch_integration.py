"""
Partie 2.2.1 -- orchestration tests for api/security/documents.py's own
start_document_batch_upload/process_upload_batch.
"""

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.database import Base
from api.models.document import DocumentStatus
from api.models.organization import Organization, OrganizationMember, OrganizationRole
from api.models.user import User
from api.security.documents import process_upload_batch, start_document_batch_upload

_REAL_PDF = b"%PDF-1.4 fake but real-looking pdf bytes"


@pytest.fixture
def _stub_s3(monkeypatch):
    monkeypatch.setattr("api.security.documents.upload_document_file", lambda org_id, doc_id, filename, content, content_type: f"documents/{org_id}/{doc_id}/{filename}")


async def _make_org(session):
    owner = User(email=f"batch-itest-{uuid.uuid4().hex[:8]}@example.com", hashed_password="irrelevant")
    session.add(owner)
    await session.flush()
    organization = Organization(name="Batch ITest Org", slug=f"batch-itest-{uuid.uuid4().hex[:8]}")
    session.add(organization)
    await session.flush()
    session.add(OrganizationMember(organization_id=organization.id, user_id=owner.id, role=OrganizationRole.owner))
    await session.commit()
    return owner, organization


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


# ------------------------------------------------- start_document_batch_upload --

async def test_start_document_batch_upload_accepts_valid_files_and_schedules_them(db_session):
    """Validation criterion: l'upload de plusieurs fichiers fonctionne."""
    owner, organization = await _make_org(db_session)
    captured = {}

    def _capture(organization_id, workspace_id, created_by, files):
        captured["files"] = files

    with patch("api.security.documents.schedule_upload_batch_processing", side_effect=_capture):
        results = await start_document_batch_upload(
            db_session, organization.id, None, owner.id,
            [("a.pdf", _REAL_PDF), ("b.pdf", _REAL_PDF)],
        )

    assert all(r["error"] is None for r in results)
    assert [f["filename"] for f in captured["files"]] == ["a.pdf", "b.pdf"]


async def test_start_document_batch_upload_rejects_an_individual_invalid_file_but_keeps_the_rest(db_session):
    """Validation criterion / vision critique 3: un fichier invalide du
    lot est rejeté sans bloquer les autres."""
    import os

    owner, organization = await _make_org(db_session)
    captured = {}

    def _capture(organization_id, workspace_id, created_by, files):
        captured["files"] = files

    with patch("api.security.documents.schedule_upload_batch_processing", side_effect=_capture):
        results = await start_document_batch_upload(
            db_session, organization.id, None, owner.id,
            [("good.pdf", _REAL_PDF), ("bad.bin", os.urandom(200))],
        )

    by_name = {r["filename"]: r for r in results}
    assert by_name["good.pdf"]["error"] is None
    assert by_name["bad.bin"]["error"] is not None
    assert [f["filename"] for f in captured["files"]] == ["good.pdf"]


async def test_start_document_batch_upload_rejects_a_workspace_from_another_organization(db_session):
    owner, organization = await _make_org(db_session)
    with pytest.raises(ValueError, match="workspace_id"):
        await start_document_batch_upload(db_session, organization.id, uuid.uuid4(), owner.id, [("a.pdf", _REAL_PDF)])


async def test_start_document_batch_upload_never_schedules_when_every_file_is_invalid(db_session):
    import os

    owner, organization = await _make_org(db_session)
    with patch("api.security.documents.schedule_upload_batch_processing") as scheduler:
        results = await start_document_batch_upload(db_session, organization.id, None, owner.id, [("bad.bin", os.urandom(200))])

    assert results[0]["error"] is not None
    scheduler.assert_not_called()


# -------------------------------------------------------- process_upload_batch --

async def test_process_upload_batch_creates_a_real_document_per_file(db_session, _stub_s3, monkeypatch):
    """Validation criterion: l'upload de plusieurs fichiers fonctionne,
    au niveau du traitement réel (Celery)."""
    owner, organization = await _make_org(db_session)
    scheduled_ids = []
    monkeypatch.setattr("api.security.documents.schedule_document_processing", lambda document_id: scheduled_ids.append(document_id))

    files = [
        {"filename": "a.pdf", "content": _REAL_PDF, "content_type": "application/pdf"},
        {"filename": "b.pdf", "content": _REAL_PDF, "content_type": "application/pdf"},
    ]
    scheduled = await process_upload_batch(db_session, organization.id, None, owner.id, files)

    assert scheduled == 2
    assert len(scheduled_ids) == 2


async def test_process_upload_batch_tolerates_a_real_s3_failure_for_one_file(db_session, monkeypatch):
    """Validation criterion / vision critique 3: que se passe-t-il si
    un fichier du lot échoue -- les autres continuent."""
    owner, organization = await _make_org(db_session)
    scheduled_ids = []
    monkeypatch.setattr("api.security.documents.schedule_document_processing", lambda document_id: scheduled_ids.append(document_id))

    def _flaky_upload(org_id, doc_id, filename, content, content_type):
        if filename == "bad.pdf":
            raise RuntimeError("S3 is down")
        return f"documents/{org_id}/{doc_id}/{filename}"

    monkeypatch.setattr("api.security.documents.upload_document_file", _flaky_upload)

    files = [
        {"filename": "good-1.pdf", "content": _REAL_PDF, "content_type": "application/pdf"},
        {"filename": "bad.pdf", "content": _REAL_PDF, "content_type": "application/pdf"},
        {"filename": "good-2.pdf", "content": _REAL_PDF, "content_type": "application/pdf"},
    ]
    scheduled = await process_upload_batch(db_session, organization.id, None, owner.id, files)

    assert scheduled == 2
    assert len(scheduled_ids) == 2

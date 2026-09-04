"""
Partie 2.2.9 -- tests for api/security/documents.py's own
reindex_document/reindex_organization/reindex_documents.

`process_document` itself (the real pipeline reindex_document reuses
unchanged) is already tested extensively elsewhere (real end-to-end,
against real S3/Postgres, in tests/test_documents_integration.py) --
mocked here at its own real call boundary, since these tests exist to
prove reindex_document/reindex_organization's own real ORCHESTRATION
logic (existence/deleted checks, real fan-out), not process_document's
own internals a second time.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.database import Base
from api.models.document import Document, DocumentStatus
from api.security.documents import reindex_document, reindex_documents, reindex_organization


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def _make_document(session, organization_id=None, status=DocumentStatus.completed.value, deleted_at=None) -> Document:
    document = Document(
        organization_id=organization_id or uuid.uuid4(), workspace_id=None, name="a.pdf",
        file_key="documents/x/a.pdf", file_size=10, file_type="application/pdf",
        status=status, created_by=None, deleted_at=deleted_at,
    )
    session.add(document)
    await session.commit()
    return document


# ------------------------------------------------------------- reindex_document --

async def test_reindex_document_calls_the_real_process_document_pipeline(db_session):
    """Validation criterion: la réindexation d'un document fonctionne;
    les chunks/embeddings sont régénérés -- via le vrai pipeline
    existant, réutilisé sans nouvelle logique."""
    document = await _make_document(db_session)

    async def _fake_process_document(db, document_id):
        document.status = DocumentStatus.completed.value
        return document

    with patch("api.security.documents.process_document", side_effect=_fake_process_document) as mock_process:
        status_value = await reindex_document(db_session, document.id)

    mock_process.assert_awaited_once_with(db_session, document.id)
    assert status_value == DocumentStatus.completed.value


async def test_reindex_document_raises_for_a_nonexistent_document(db_session):
    with pytest.raises(ValueError, match="not a registered"):
        await reindex_document(db_session, uuid.uuid4())


async def test_reindex_document_raises_for_a_soft_deleted_document(db_session):
    """Validation criterion / cohérence avec 2.2.8 -- un document
    supprimé logiquement ne doit pas être réindexé."""
    import datetime as dt

    document = await _make_document(db_session, deleted_at=dt.datetime.now(dt.timezone.utc))
    with pytest.raises(ValueError, match="not a registered, non-deleted"):
        await reindex_document(db_session, document.id)


# ---------------------------------------------------------- reindex_documents --

def test_reindex_documents_schedules_one_task_per_document_with_a_real_stagger(monkeypatch):
    from api.security import documents as documents_module

    calls = []

    class _FakeTask:
        def apply_async(self, args, countdown):
            calls.append((args, countdown))

    monkeypatch.setattr("api.tasks.reindex.reindex_document_task", _FakeTask())

    document_ids = [uuid.uuid4(), uuid.uuid4()]
    scheduled = documents_module.reindex_documents(document_ids)

    assert scheduled == 2
    assert calls[0][0] == [str(document_ids[0])]
    assert calls[0][1] == 0
    assert calls[1][1] == documents_module._REINDEX_STAGGER_SECONDS


def test_reindex_documents_tolerates_a_broker_failure_for_one_document(monkeypatch):
    from api.security import documents as documents_module

    good_id, bad_id = uuid.uuid4(), uuid.uuid4()
    calls = []

    class _FlakyTask:
        def apply_async(self, args, countdown):
            if args[0] == str(bad_id):
                raise ConnectionError("broker unreachable")
            calls.append(args)

    monkeypatch.setattr("api.tasks.reindex.reindex_document_task", _FlakyTask())

    scheduled = documents_module.reindex_documents([good_id, bad_id, uuid.uuid4()])

    assert scheduled == 2
    assert len(calls) == 2


# ------------------------------------------------------- reindex_organization --

async def test_reindex_organization_fans_out_to_every_real_non_deleted_document(db_session):
    """Validation criterion: la réindexation de tous les documents
    fonctionne, gérée par un vrai fan-out Celery (pas une boucle
    synchrone géante)."""
    import datetime as dt

    organization_id = uuid.uuid4()
    kept_one = await _make_document(db_session, organization_id=organization_id)
    kept_two = await _make_document(db_session, organization_id=organization_id)
    await _make_document(db_session, organization_id=organization_id, deleted_at=dt.datetime.now(dt.timezone.utc))  # excluded
    await _make_document(db_session)  # a different organization -- excluded

    with patch("api.security.documents.reindex_documents", return_value=2) as mock_fan_out:
        scheduled = await reindex_organization(db_session, organization_id)

    assert scheduled == 2
    fanned_out_ids = set(mock_fan_out.call_args.args[0])
    assert fanned_out_ids == {kept_one.id, kept_two.id}

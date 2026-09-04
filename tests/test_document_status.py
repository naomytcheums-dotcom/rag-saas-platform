"""
Partie 2.2.11 -- tests for the two new
Document.indexing_started_at/indexing_error columns, set by
api/security/documents.py's own process_document at its two real
status-transition points.

A real, successful run of process_document (proving indexing_started_at
is set and indexing_error stays None on the `completed` path) is only
exercised end to end in tests/test_documents_integration.py, against
real Postgres/S3 -- the same established split as every other
process_document behavior in this codebase (extraction/chunking/
embeddings are real infrastructure the fast SQLite suite never runs).
What's tested here instead, fast and without real infra: the `failed`
path's own field-setting, forced by mocking `download_document_file`
(process_document's own very first real step) to raise -- no tokenizer,
no embeddings, no S3 needed to reach that code path.
"""

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.database import Base
from api.models.document import Document, DocumentStatus
from api.security.documents import process_document

_REAL_PDF_MAGIC = b"%PDF-1.4\n%fake but real-looking pdf bytes\n"


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def _make_document(session, indexing_error=None) -> Document:
    document = Document(
        organization_id=uuid.uuid4(), workspace_id=None, name="a.pdf",
        file_key="documents/x/a.pdf", file_size=len(_REAL_PDF_MAGIC), file_type="application/pdf",
        status=DocumentStatus.pending.value, created_by=None, indexing_error=indexing_error,
    )
    session.add(document)
    await session.commit()
    return document


async def test_process_document_records_a_real_error_and_start_time_on_failure(db_session):
    """Validation criterion: le statut et l'erreur d'indexation sont
    consultables après un échec réel."""
    document = await _make_document(db_session)

    with patch("api.security.documents.download_document_file", side_effect=RuntimeError("S3 object not found")):
        updated = await process_document(db_session, document.id)

    assert updated.status == DocumentStatus.failed.value
    assert updated.indexing_error == "S3 object not found"
    assert updated.indexing_started_at is not None


async def test_process_document_clears_a_stale_error_from_a_prior_attempt(db_session):
    """Vision critique -- une réindexation en cours ne doit jamais
    laisser une ancienne erreur affichée pendant qu'elle retente,
    seulement la nouvelle erreur réelle si elle échoue à nouveau."""
    document = await _make_document(db_session, indexing_error="a stale error from three attempts ago")

    with patch("api.security.documents.download_document_file", side_effect=RuntimeError("a brand new, different failure")):
        updated = await process_document(db_session, document.id)

    assert updated.indexing_error == "a brand new, different failure"


async def test_process_document_raises_for_a_nonexistent_document(db_session):
    with pytest.raises(ValueError, match="not a registered document"):
        await process_document(db_session, uuid.uuid4())

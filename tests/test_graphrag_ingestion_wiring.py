"""Real, wired GraphRAG ingestion: `process_document`
(api/security/documents.py) now genuinely calls
`api.services.graph_rag.ingest_into_graph` with every real, non-empty,
ALREADY PII-masked section text once a document finishes processing --
closing the gap `api/services/graph_rag.py`'s own module docstring
honestly flagged (a real, working building block nothing real called
yet). Same fast, standalone SQLite fixture convention as
tests/test_chunking_strategy_wiring.py -- `download_document_file`/
`extract_document_content` mocked (S3/per-format parsing are real
infrastructure this fast suite never runs), `ingest_into_graph` itself
mocked at its own clean, already-tested boundary (real LightRAG entity
extraction is covered by tests/test_graph_rag.py)."""

import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.database import Base
from api.models.document import Document, DocumentStatus
from api.models.organization_settings import OrganizationSettings
from api.security.documents import MARKDOWN_CONTENT_TYPE, process_document

_TEXT = "# Real Section\n\nReal, non-empty content about the real subject matter of this document."


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def _make_document(session, organization_id) -> Document:
    document = Document(
        organization_id=organization_id, workspace_id=None, name="doc.md",
        file_key="documents/x/doc.md", file_size=len(_TEXT), file_type=MARKDOWN_CONTENT_TYPE,
        status=DocumentStatus.pending.value, created_by=None,
    )
    session.add(document)
    await session.commit()
    return document


def _mock_extraction(monkeypatch):
    monkeypatch.setattr("api.security.documents.download_document_file", lambda file_key: b"fake bytes, never really parsed")
    monkeypatch.setattr(
        "api.security.documents.extract_document_content",
        lambda tmp_path, file_type, pdf_engine="pymupdf": {
            "metadata": {}, "sections": [{"text": _TEXT, "metadata": {}}], "tables": [], "image_count": 0,
        },
    )


async def test_process_document_ingests_into_the_graph_when_enabled(db_session, monkeypatch):
    """Validation criterion: an organization with graphrag_enabled=True
    gets its real section text ingested into its own real graph."""
    org_id = uuid.uuid4()
    document = await _make_document(db_session, org_id)
    db_session.add(OrganizationSettings(organization_id=org_id, settings={"graphrag_enabled": True}))
    await db_session.commit()
    _mock_extraction(monkeypatch)

    mock_ingest = AsyncMock()
    monkeypatch.setattr("api.services.graph_rag.ingest_into_graph", mock_ingest)

    updated = await process_document(db_session, document.id)

    assert updated.status == DocumentStatus.completed.value
    mock_ingest.assert_awaited_once()
    call_args = mock_ingest.call_args
    assert call_args.args[0] == org_id
    assert "Real, non-empty content about the real subject matter" in call_args.args[1][0]


async def test_process_document_never_ingests_into_the_graph_when_disabled(db_session, monkeypatch):
    """Real, deliberate default: an organization that never touches
    graphrag_enabled pays zero real cost -- no graph call at all."""
    org_id = uuid.uuid4()
    document = await _make_document(db_session, org_id)
    _mock_extraction(monkeypatch)

    mock_ingest = AsyncMock()
    monkeypatch.setattr("api.services.graph_rag.ingest_into_graph", mock_ingest)

    updated = await process_document(db_session, document.id)

    assert updated.status == DocumentStatus.completed.value
    mock_ingest.assert_not_awaited()


async def test_process_document_completes_even_if_graph_ingestion_fails(db_session, monkeypatch):
    """Real, fail-open discipline: a real graph-ingestion failure must
    never fail a real document upload that would otherwise succeed --
    same reasoning as this module's own metadata-enrichment step."""
    org_id = uuid.uuid4()
    document = await _make_document(db_session, org_id)
    db_session.add(OrganizationSettings(organization_id=org_id, settings={"graphrag_enabled": True}))
    await db_session.commit()
    _mock_extraction(monkeypatch)

    async def _raise(*args, **kwargs):
        raise RuntimeError("real, unexpected graph ingestion failure")

    monkeypatch.setattr("api.services.graph_rag.ingest_into_graph", _raise)

    updated = await process_document(db_session, document.id)

    assert updated.status == DocumentStatus.completed.value


async def test_process_document_masks_pii_before_graph_ingestion_when_both_enabled(db_session, monkeypatch):
    """Real, honest privacy discipline: when both pii_masking_enabled
    and graphrag_enabled are on, the graph must receive the SAME
    masked text as what actually gets chunked/embedded -- never raw PII
    underneath a masked chunk."""
    org_id = uuid.uuid4()
    document = await _make_document(db_session, org_id)
    db_session.add(OrganizationSettings(organization_id=org_id, settings={"graphrag_enabled": True, "pii_masking_enabled": True}))
    await db_session.commit()
    _mock_extraction(monkeypatch)

    monkeypatch.setattr("api.services.pii_detection.mask_pii", lambda text: ("[REDACTED SECTION]", []))
    mock_ingest = AsyncMock()
    monkeypatch.setattr("api.services.graph_rag.ingest_into_graph", mock_ingest)

    await process_document(db_session, document.id)

    mock_ingest.assert_awaited_once()
    assert mock_ingest.call_args.args[1] == ["[REDACTED SECTION]"]

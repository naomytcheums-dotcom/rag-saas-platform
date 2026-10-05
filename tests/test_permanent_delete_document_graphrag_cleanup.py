"""Hardening Mission, Phase 6 -- REGRESSION for a real, confirmed GDPR/
right-to-be-forgotten gap: `api.security.documents.permanent_delete_document`
used to purge the S3 object + the DB row but left any real GraphRAG
entities/relations a document contributed orphaned forever. Mocked at
`delete_document_from_graph`'s own already-tested boundary
(tests/test_graph_rag.py covers the real LightRAG call itself) --
these tests prove the real WIRING: called when graphrag_enabled, with
the right organization_id/document_id, skipped otherwise, and never
blocking the real deletion on a real cleanup failure."""

import uuid
from unittest.mock import AsyncMock

from api.models.document import Document, DocumentStatus
from api.models.organization import Organization
from api.security.documents import permanent_delete_document
from api.security.organization_settings import update_org_settings


async def _make_org_and_document(db_session, name, graphrag_enabled: bool):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    if graphrag_enabled:
        await update_org_settings(db_session, org.id, {"graphrag_enabled": True})
    document = Document(
        organization_id=org.id, name="doc.pdf", file_key=f"documents/{uuid.uuid4()}/doc.pdf",
        file_size=10, file_type="application/pdf", status=DocumentStatus.completed.value,
    )
    db_session.add(document)
    await db_session.flush()
    await db_session.commit()
    return org, document


async def test_permanent_delete_cleans_up_the_real_graph_when_graphrag_is_enabled(monkeypatch, db_session):
    org, document = await _make_org_and_document(db_session, "GraphRAG Cleanup Org", graphrag_enabled=True)
    monkeypatch.setattr("api.security.documents.delete_document_file", lambda key: None)
    fake_delete = AsyncMock()
    monkeypatch.setattr("api.services.graph_rag.delete_document_from_graph", fake_delete)

    await permanent_delete_document(db_session, document.id)
    await db_session.commit()

    fake_delete.assert_awaited_once()
    args = fake_delete.await_args.args
    assert args[0] == org.id
    assert args[1] == document.id


async def test_permanent_delete_skips_graph_cleanup_when_graphrag_is_disabled(monkeypatch, db_session):
    _org, document = await _make_org_and_document(db_session, "No GraphRAG Org", graphrag_enabled=False)
    monkeypatch.setattr("api.security.documents.delete_document_file", lambda key: None)
    fake_delete = AsyncMock()
    monkeypatch.setattr("api.services.graph_rag.delete_document_from_graph", fake_delete)

    await permanent_delete_document(db_session, document.id)
    await db_session.commit()

    fake_delete.assert_not_awaited()


async def test_permanent_delete_still_succeeds_when_graph_cleanup_fails(monkeypatch, db_session):
    """Real, fail-open discipline: a GraphRAG cleanup failure must never
    block a real, already-authorized permanent deletion."""
    _org, document = await _make_org_and_document(db_session, "Flaky GraphRAG Org", graphrag_enabled=True)
    monkeypatch.setattr("api.security.documents.delete_document_file", lambda key: None)
    monkeypatch.setattr("api.services.graph_rag.delete_document_from_graph", AsyncMock(side_effect=RuntimeError("LightRAG unreachable")))

    await permanent_delete_document(db_session, document.id)  # must not raise
    await db_session.commit()

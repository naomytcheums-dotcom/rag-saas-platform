"""api/services/rag_provenance.py -- real provenance chain built
entirely from this codebase's own real, relational data (Response ->
Citation -> Document), no mocking needed."""

import datetime as dt
import uuid

from api.services.rag_provenance import get_response_provenance


async def _make_org_and_document(db_session, source_url=None):
    from api.models.document import Document, DocumentStatus
    from api.models.organization import Organization

    org = Organization(name="Provenance Org", slug=f"provenance-org-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    document = Document(
        organization_id=org.id, workspace_id=None, name="policy.pdf", source_url=source_url,
        file_key="documents/x/policy.pdf", file_size=1234, file_type="application/pdf",
        status=DocumentStatus.completed.value, created_by=None,
    )
    db_session.add(document)
    await db_session.flush()
    return org, document


async def _make_response(db_session, org_id):
    from api.models.response import Response

    response = Response(organization_id=org_id, workspace_id=None, query="What is the refund policy?", answer="Refunds within 30 days [1].")
    db_session.add(response)
    await db_session.flush()
    return response


async def test_get_response_provenance_returns_none_for_an_unknown_response(db_session):
    result = await get_response_provenance(db_session, uuid.uuid4())
    assert result is None


async def test_get_response_provenance_walks_a_real_citation_to_its_real_source_document(db_session):
    from api.models.citation import Citation

    org, document = await _make_org_and_document(db_session, source_url="https://example.com/policy")
    response = await _make_response(db_session, org.id)
    db_session.add(Citation(
        response_id=response.id, document_id=document.id, chunk_id=None, text="Refunds within 30 days.",
        relevance_score=0.9, citation_number=1, document_name=document.name, document_type=document.file_type,
    ))
    await db_session.commit()

    result = await get_response_provenance(db_session, response.id)

    assert result["response_id"] == response.id
    assert result["citation_count"] == 1
    source = result["sources"][0]
    assert source["document_name"] == "policy.pdf"
    assert source["source_url"] == "https://example.com/policy"


async def test_get_response_provenance_falls_back_to_denormalized_fields_once_document_id_is_null(db_session):
    """Validation criterion: once a real source document is deleted
    (the DB's own real `SET NULL` on `Citation.document_id` already
    guarantees `document_id` is NULL by the time this ever runs, never
    a dangling reference this module would need to detect itself), the
    real chain still shows the real source name/type from the
    citation's own real, denormalized fields -- never silently
    dropped, never a crash on a NULL foreign key."""
    from api.models.citation import Citation

    org, document = await _make_org_and_document(db_session)
    response = await _make_response(db_session, org.id)
    citation = Citation(
        response_id=response.id, document_id=document.id, chunk_id=None, text="Refunds within 30 days.",
        relevance_score=0.9, citation_number=1, document_name=document.name, document_type=document.file_type,
    )
    db_session.add(citation)
    await db_session.flush()

    # Simulate the real SET NULL that happens when the source document is deleted.
    citation.document_id = None
    await db_session.commit()

    result = await get_response_provenance(db_session, response.id)

    source = result["sources"][0]
    assert source["document_name"] == "policy.pdf"  # from the real, denormalized field
    assert source["document_type"] == "application/pdf"


async def test_get_response_provenance_returns_real_citations_in_order(db_session):
    from api.models.citation import Citation

    org, document = await _make_org_and_document(db_session)
    response = await _make_response(db_session, org.id)
    db_session.add(Citation(
        response_id=response.id, document_id=document.id, text="Second point.", relevance_score=0.7,
        citation_number=2, document_name=document.name, document_type=document.file_type,
    ))
    db_session.add(Citation(
        response_id=response.id, document_id=document.id, text="First point.", relevance_score=0.9,
        citation_number=1, document_name=document.name, document_type=document.file_type,
    ))
    await db_session.commit()

    result = await get_response_provenance(db_session, response.id)
    assert [s["citation_number"] for s in result["sources"]] == [1, 2]

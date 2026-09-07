"""Partie 6.1.5 -- chunk ID. Fast SQLite suite."""

import uuid

from sqlalchemy import select

from api.models.citation import Citation
from api.models.document import Document, DocumentChunk, DocumentStatus
from api.models.organization import Organization
from api.models.response import Response
from api.models.user import User
from api.services.citation_chunk import (
    enrich_citation_with_chunk, enrich_citations_with_chunk, extract_chunk_info, format_chunk_reference,
    get_chunk_content,
)


async def _make_org(db_session, name):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


async def _make_document(db_session, org_id, name="doc.pdf"):
    document = Document(
        organization_id=org_id, name=name, file_key=f"documents/{uuid.uuid4()}/{name}",
        file_size=10, file_type="application/pdf", status=DocumentStatus.completed.value,
    )
    db_session.add(document)
    await db_session.flush()
    return document


async def _make_chunk(db_session, document, org_id, content="chunk text", chunk_index=None):
    chunk = DocumentChunk(document_id=document.id, organization_id=org_id, content=content, chunk_index=chunk_index)
    db_session.add(chunk)
    await db_session.flush()
    return chunk


async def _make_response(db_session, org_id):
    response = Response(organization_id=org_id, query="q", answer="a")
    db_session.add(response)
    await db_session.flush()
    return response


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


# --------------------------------------- extract_chunk_info --


def test_extract_chunk_info_reads_a_real_chunk_shaped_dict():
    """Validation criterion: l'identifiant du chunk est accessible."""
    info = extract_chunk_info({"chunk_id": "c1", "document_id": "d1", "content": "hello world", "chunk_index": 3})
    assert info == {"chunk_id": "c1", "document_id": "d1", "chunk_index": 3, "content_length": 11}


def test_extract_chunk_info_accepts_a_real_orm_object_too():
    class _FakeChunk:
        id = uuid.UUID("11111111-1111-1111-1111-111111111111")
        document_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
        content = "abc"
        chunk_index = 5

    info = extract_chunk_info(_FakeChunk())
    assert info["content_length"] == 3
    assert info["chunk_index"] == 5
    assert info["chunk_id"] == "11111111-1111-1111-1111-111111111111"


def test_extract_chunk_info_is_honest_about_a_legacy_chunk_with_no_real_index():
    """Validation criterion: robustesse -- chunk antérieur à la fonctionnalité."""
    info = extract_chunk_info({"chunk_id": "c1", "document_id": "d1", "content": "x"})
    assert info["chunk_index"] is None


# --------------------------------------- get_chunk_content --


async def test_get_chunk_content_returns_the_real_live_text(db_session):
    org = await _make_org(db_session, "Chunk Content Org")
    document = await _make_document(db_session, org.id)
    chunk = await _make_chunk(db_session, document, org.id, content="the real chunk text", chunk_index=1)
    await db_session.commit()

    assert await get_chunk_content(db_session, chunk.id) == "the real chunk text"


async def test_get_chunk_content_returns_none_for_an_unknown_chunk(db_session):
    assert await get_chunk_content(db_session, uuid.uuid4()) is None


# --------------------------------------- format_chunk_reference --


def test_format_chunk_reference_renders_a_real_human_readable_label():
    citation = Citation(response_id=uuid.uuid4(), text="t", relevance_score=0.9, citation_number=1, chunk_index=3)
    assert format_chunk_reference(citation) == "Chunk #3"


def test_format_chunk_reference_is_honestly_empty_when_the_index_is_unknown():
    citation = Citation(response_id=uuid.uuid4(), text="t", relevance_score=0.9, citation_number=1)
    assert format_chunk_reference(citation) == ""


# --------------------------------------- add_citations_to_response now populates chunk_index --


async def test_add_citations_to_response_populates_real_chunk_index_from_the_chunk(db_session):
    """Validation criterion: l'index est capturé à la création de la citation,
    à partir du vrai chunk_index persisté (migration 0068), sans requête
    supplémentaire."""
    from api.services.citations import add_citations_to_response

    org = await _make_org(db_session, "Chunk Index Org")
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    chunks = [
        {"chunk_id": str(uuid.uuid4()), "document_id": str(uuid.uuid4()), "content": "second", "score": 0.9,
         "document_name": "doc.pdf", "file_type": "application/pdf", "chunk_index": 2},
    ]

    citations = await add_citations_to_response(db_session, response, chunks)
    await db_session.commit()

    assert citations[0].chunk_index == 2


async def test_add_citations_to_response_is_honest_when_the_chunk_has_no_real_index(db_session):
    from api.services.citations import add_citations_to_response

    org = await _make_org(db_session, "Chunk Index Org 2")
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    chunks = [
        {"chunk_id": str(uuid.uuid4()), "document_id": str(uuid.uuid4()), "content": "legacy", "score": 0.9,
         "document_name": "doc.pdf", "file_type": "application/pdf"},
    ]

    citations = await add_citations_to_response(db_session, response, chunks)
    await db_session.commit()

    assert citations[0].chunk_index is None


# --------------------------------------- enrich_citation_with_chunk --


async def test_enrich_citation_with_chunk_refreshes_from_the_real_live_chunk(db_session):
    """Validation criterion: cohérence -- l'index vient du vrai chunk."""
    org = await _make_org(db_session, "Enrich Chunk Org")
    document = await _make_document(db_session, org.id)
    chunk = await _make_chunk(db_session, document, org.id, content="second", chunk_index=2)
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    citation = Citation(
        response_id=response.id, document_id=document.id, chunk_id=chunk.id, text="t", relevance_score=0.9,
        citation_number=1, chunk_index=99,
    )
    db_session.add(citation)
    await db_session.commit()

    enriched = await enrich_citation_with_chunk(db_session, citation)
    assert enriched.chunk_index == 2


async def test_enrich_citation_with_chunk_is_a_real_no_op_without_a_real_chunk_id(db_session):
    org = await _make_org(db_session, "Enrich Chunk Org 2")
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    citation = Citation(response_id=response.id, chunk_id=None, text="t", relevance_score=0.9, citation_number=1)
    db_session.add(citation)
    await db_session.commit()

    enriched = await enrich_citation_with_chunk(db_session, citation)
    assert enriched.chunk_index is None


async def test_enrich_citation_with_chunk_keeps_the_real_snapshot_when_the_chunk_is_gone(db_session):
    """Validation criterion: robustesse -- chunk supprimé."""
    org = await _make_org(db_session, "Enrich Chunk Org 3")
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    citation = Citation(
        response_id=response.id, chunk_id=uuid.uuid4(), text="t", relevance_score=0.9, citation_number=1, chunk_index=5,
    )
    db_session.add(citation)
    await db_session.commit()

    enriched = await enrich_citation_with_chunk(db_session, citation)
    assert enriched.chunk_index == 5


async def test_enrich_citation_with_chunk_keeps_the_real_snapshot_when_the_live_chunk_has_no_real_index(db_session):
    """Validation criterion: robustesse -- chunk existant mais antérieur à la fonctionnalité."""
    org = await _make_org(db_session, "Enrich Chunk Org 4")
    document = await _make_document(db_session, org.id)
    chunk = await _make_chunk(db_session, document, org.id, content="legacy", chunk_index=None)
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    citation = Citation(
        response_id=response.id, document_id=document.id, chunk_id=chunk.id, text="t", relevance_score=0.9,
        citation_number=1, chunk_index=7,
    )
    db_session.add(citation)
    await db_session.commit()

    enriched = await enrich_citation_with_chunk(db_session, citation)
    assert enriched.chunk_index == 7


async def test_enrich_citations_with_chunk_enriches_every_real_citation(db_session):
    org = await _make_org(db_session, "Enrich Chunk Org 5")
    document = await _make_document(db_session, org.id)
    chunk = await _make_chunk(db_session, document, org.id, content="first", chunk_index=1)
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    citations = [
        Citation(response_id=response.id, document_id=document.id, chunk_id=chunk.id, text="t", relevance_score=0.9, citation_number=1),
    ]
    db_session.add_all(citations)
    await db_session.commit()

    enriched = await enrich_citations_with_chunk(db_session, citations)
    assert enriched[0].chunk_index == 1


# --------------------------------------- endpoint --


async def test_citation_endpoint_returns_real_chunk_index(client, db_session, register_payload):
    """Validation criterion: la récupération fonctionne + permissions respectées."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_response = await client.post("/organizations", json={"name": "Chunk Endpoint Org"}, headers=_auth_header(owner_token))
    org_id = uuid.UUID(org_response.json()["id"])
    document = await _make_document(db_session, org_id)
    chunk = await _make_chunk(db_session, document, org_id, content="second", chunk_index=2)
    response = await _make_response(db_session, org_id)
    await db_session.commit()
    citation = Citation(
        response_id=response.id, document_id=document.id, chunk_id=chunk.id, text="t", relevance_score=0.9, citation_number=1,
    )
    db_session.add(citation)
    await db_session.commit()

    api_response = await client.get(f"/citations/{citation.id}", headers=_auth_header(owner_token))
    assert api_response.status_code == 200
    assert api_response.json()["chunk_index"] == 2

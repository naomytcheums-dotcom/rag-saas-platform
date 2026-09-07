"""Partie 6.1.3 -- page PDF / section. Fast SQLite suite."""

import uuid

from sqlalchemy import select

from api.models.citation import Citation
from api.models.document import Document, DocumentChunk, DocumentStatus
from api.models.organization import Organization
from api.models.response import Response
from api.models.user import User
from api.services.citation_location import (
    enrich_citation_with_location, enrich_citations_with_location, extract_heading_from_chunk,
    extract_page_from_chunk, extract_section_from_chunk, format_citation_location,
)
from api.services.citations import add_citations_to_response


async def _make_org(db_session, name):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


async def _make_document(db_session, org_id, name="doc.pdf", file_type="application/pdf"):
    document = Document(
        organization_id=org_id, name=name, file_key=f"documents/{uuid.uuid4()}/{name}",
        file_size=10, file_type=file_type, status=DocumentStatus.completed.value,
    )
    db_session.add(document)
    await db_session.flush()
    return document


async def _make_chunk_row(db_session, document, org_id, metadata_json):
    chunk = DocumentChunk(document_id=document.id, organization_id=org_id, content="chunk text", metadata_json=metadata_json)
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


# --------------------------------------- extract_page_from_chunk / extract_section_from_chunk --


def test_extract_page_from_chunk_reads_the_real_pdf_page():
    """Validation criterion: le numéro de page est affiché pour les PDF."""
    assert extract_page_from_chunk({"metadata_json": {"page": 12}}) == 12


def test_extract_page_from_chunk_returns_none_when_missing():
    """Validation criterion: robustesse -- informations manquantes."""
    assert extract_page_from_chunk({"metadata_json": {}}) is None


def test_extract_section_from_chunk_reads_the_real_markdown_heading():
    """Validation criterion: le nom de la section est affiché pour les documents structurés."""
    assert extract_section_from_chunk({"metadata_json": {"heading": "Introduction", "level": 2}}) == "H2: Introduction"


def test_extract_section_from_chunk_without_a_level_returns_the_bare_heading():
    assert extract_section_from_chunk({"metadata_json": {"heading": "Intro"}}) == "Intro"


def test_extract_section_from_chunk_returns_none_when_no_real_heading():
    assert extract_section_from_chunk({"metadata_json": {}}) is None


def test_extract_heading_from_chunk():
    assert extract_heading_from_chunk({"metadata_json": {"heading": "Conclusion"}}) == "Conclusion"


def test_extractors_accept_a_real_document_chunk_object_too():
    class _FakeChunk:
        metadata_json = {"page": 3}

    assert extract_page_from_chunk(_FakeChunk()) == 3


# --------------------------------------- format_citation_location --


def test_format_citation_location_prefers_the_real_page():
    citation = Citation(response_id=uuid.uuid4(), text="t", relevance_score=0.9, citation_number=1, source_page=5, source_heading="Intro")
    assert format_citation_location(citation) == "p. 5"


def test_format_citation_location_falls_back_to_the_real_heading():
    citation = Citation(response_id=uuid.uuid4(), text="t", relevance_score=0.9, citation_number=1, source_heading="Intro")
    assert format_citation_location(citation) == "Intro"


def test_format_citation_location_is_honestly_empty_when_nothing_is_known():
    citation = Citation(response_id=uuid.uuid4(), text="t", relevance_score=0.9, citation_number=1)
    assert format_citation_location(citation) == ""


# --------------------------------------- add_citations_to_response now populates location --


async def test_add_citations_to_response_populates_real_location_at_creation_time(db_session):
    """Validation criterion: les informations de page/section sont
    extraites des métadonnées du chunk."""
    org = await _make_org(db_session, "Location Org")
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    chunks = [{"chunk_id": str(uuid.uuid4()), "document_id": str(uuid.uuid4()), "content": "c", "score": 0.9,
               "document_name": "d.pdf", "file_type": "pdf", "metadata_json": {"page": 7}}]

    citations = await add_citations_to_response(db_session, response, chunks)
    await db_session.commit()

    assert citations[0].source_page == 7


# --------------------------------------- enrich_citation_with_location --


async def test_enrich_citation_with_location_refreshes_from_the_real_live_chunk(db_session):
    """Validation criterion: cohérence -- extrait des métadonnées du chunk."""
    org = await _make_org(db_session, "Location Org 2")
    document = await _make_document(db_session, org.id)
    chunk = await _make_chunk_row(db_session, document, org.id, {"page": 42})
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    citation = Citation(response_id=response.id, chunk_id=chunk.id, text="t", relevance_score=0.9, citation_number=1)
    db_session.add(citation)
    await db_session.commit()

    enriched = await enrich_citation_with_location(db_session, citation)
    assert enriched.source_page == 42


async def test_enrich_citation_with_location_is_a_real_no_op_without_a_real_chunk_id(db_session):
    org = await _make_org(db_session, "Location Org 3")
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    citation = Citation(response_id=response.id, chunk_id=None, text="t", relevance_score=0.9, citation_number=1, source_page=99)
    db_session.add(citation)
    await db_session.commit()

    enriched = await enrich_citation_with_location(db_session, citation)
    assert enriched.source_page == 99


async def test_enrich_citation_with_location_keeps_the_real_snapshot_when_the_chunk_is_gone(db_session):
    """Validation criterion: robustesse -- chunk supprimé."""
    org = await _make_org(db_session, "Location Org 4")
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    citation = Citation(response_id=response.id, chunk_id=uuid.uuid4(), text="t", relevance_score=0.9, citation_number=1, source_page=13)
    db_session.add(citation)
    await db_session.commit()

    enriched = await enrich_citation_with_location(db_session, citation)
    assert enriched.source_page == 13


async def test_enrich_citations_with_location_enriches_every_real_citation(db_session):
    org = await _make_org(db_session, "Location Org 5")
    document = await _make_document(db_session, org.id)
    chunk = await _make_chunk_row(db_session, document, org.id, {"heading": "Methods"})
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    citations = [Citation(response_id=response.id, chunk_id=chunk.id, text="t", relevance_score=0.9, citation_number=1)]
    db_session.add_all(citations)
    await db_session.commit()

    enriched = await enrich_citations_with_location(db_session, citations)
    assert enriched[0].source_heading == "Methods"


# --------------------------------------- endpoint --


async def test_citation_endpoint_returns_real_location_info(client, db_session, register_payload):
    """Validation criterion: le formatage fonctionne + permissions respectées."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_response = await client.post("/organizations", json={"name": "Location Endpoint Org"}, headers=_auth_header(owner_token))
    org_id = uuid.UUID(org_response.json()["id"])
    document = await _make_document(db_session, org_id)
    chunk = await _make_chunk_row(db_session, document, org_id, {"page": 21})
    response = await _make_response(db_session, org_id)
    await db_session.commit()
    citation = Citation(response_id=response.id, chunk_id=chunk.id, document_id=document.id, text="t", relevance_score=0.9, citation_number=1)
    db_session.add(citation)
    await db_session.commit()

    api_response = await client.get(f"/citations/{citation.id}", headers=_auth_header(owner_token))
    assert api_response.status_code == 200
    assert api_response.json()["source_page"] == 21

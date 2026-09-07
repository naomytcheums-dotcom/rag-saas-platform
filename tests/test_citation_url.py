"""Partie 6.1.4 -- source URL. Fast SQLite suite."""

import uuid

from sqlalchemy import select

from api.models.citation import Citation
from api.models.document import Document, DocumentStatus
from api.models.response import Response
from api.models.user import User
from api.services.citation_url import (
    enrich_citation_with_url, enrich_citations_with_url, extract_url_from_chunk,
    extract_url_from_document, format_citation_url, is_url_valid,
)


async def _make_org(db_session, name):
    from api.models.organization import Organization

    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


async def _make_document(db_session, org_id, name="page.html", source_url=None):
    document = Document(
        organization_id=org_id, name=name, file_key=f"documents/{uuid.uuid4()}/{name}",
        file_size=10, file_type="text/html", status=DocumentStatus.completed.value, source_url=source_url,
    )
    db_session.add(document)
    await db_session.flush()
    return document


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


# --------------------------------------- is_url_valid --


def test_is_url_valid_accepts_a_real_https_url():
    assert is_url_valid("https://example.com/page") is True


def test_is_url_valid_accepts_a_real_http_url():
    assert is_url_valid("http://example.com/page") is True


def test_is_url_valid_rejects_none():
    assert is_url_valid(None) is False


def test_is_url_valid_rejects_an_empty_string():
    assert is_url_valid("") is False


def test_is_url_valid_rejects_a_javascript_scheme():
    """Validation criterion: robustesse -- une URL malveillante n'est pas rendue cliquable."""
    assert is_url_valid("javascript:alert(1)") is False


def test_is_url_valid_rejects_a_relative_path():
    assert is_url_valid("/some/path") is False


# --------------------------------------- extract_url_from_document / extract_url_from_chunk --


def test_extract_url_from_document_reads_the_real_source_url():
    """Validation criterion: l'URL source est affichée quand elle existe."""
    assert extract_url_from_document({"source_url": "https://example.com/doc"}) == "https://example.com/doc"


def test_extract_url_from_document_returns_none_when_absent():
    """Validation criterion: robustesse -- document sans URL (upload de fichier)."""
    assert extract_url_from_document({"source_url": None}) is None


def test_extract_url_from_document_rejects_an_invalid_url():
    assert extract_url_from_document({"source_url": "javascript:alert(1)"}) is None


def test_extract_url_from_document_accepts_a_real_orm_object_too():
    class _FakeDocument:
        source_url = "https://example.com/from-orm"

    assert extract_url_from_document(_FakeDocument()) == "https://example.com/from-orm"


def test_extract_url_from_chunk_reads_the_same_real_joined_in_source_url():
    """Validation criterion: cohérence -- la même URL que le document parent."""
    assert extract_url_from_chunk({"source_url": "https://example.com/chunk-parent"}) == "https://example.com/chunk-parent"


# --------------------------------------- format_citation_url --


def test_format_citation_url_renders_a_real_clickable_link():
    citation = Citation(
        response_id=uuid.uuid4(), text="t", relevance_score=0.9, citation_number=1,
        source_url="https://example.com/doc", document_name="doc.html",
    )
    assert format_citation_url(citation) == "[doc.html](https://example.com/doc)"


def test_format_citation_url_is_honestly_empty_when_no_real_url_is_known():
    citation = Citation(response_id=uuid.uuid4(), text="t", relevance_score=0.9, citation_number=1)
    assert format_citation_url(citation) == ""


# --------------------------------------- enrich_citation_with_url --


async def test_enrich_citation_with_url_refreshes_from_the_real_live_document(db_session):
    """Validation criterion: cohérence -- l'URL vient de la table documents."""
    org = await _make_org(db_session, "URL Org")
    document = await _make_document(db_session, org.id, source_url="https://example.com/original")
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    citation = Citation(response_id=response.id, document_id=document.id, text="t", relevance_score=0.9, citation_number=1)
    db_session.add(citation)
    await db_session.commit()

    document.source_url = "https://example.com/updated"
    await db_session.commit()

    enriched = await enrich_citation_with_url(db_session, citation)
    assert enriched.source_url == "https://example.com/updated"


async def test_enrich_citation_with_url_is_a_real_no_op_without_a_real_document_id(db_session):
    org = await _make_org(db_session, "URL Org 2")
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    citation = Citation(
        response_id=response.id, document_id=None, text="t", relevance_score=0.9, citation_number=1,
        source_url="https://example.com/snapshot",
    )
    db_session.add(citation)
    await db_session.commit()

    enriched = await enrich_citation_with_url(db_session, citation)
    assert enriched.source_url == "https://example.com/snapshot"


async def test_enrich_citation_with_url_keeps_the_real_snapshot_when_the_document_is_gone(db_session):
    """Validation criterion: robustesse -- document supprimé."""
    org = await _make_org(db_session, "URL Org 3")
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    citation = Citation(
        response_id=response.id, document_id=uuid.uuid4(), text="t", relevance_score=0.9, citation_number=1,
        source_url="https://example.com/historical",
    )
    db_session.add(citation)
    await db_session.commit()

    enriched = await enrich_citation_with_url(db_session, citation)
    assert enriched.source_url == "https://example.com/historical"


async def test_enrich_citation_with_url_clears_a_stale_snapshot_when_the_document_no_longer_has_one(db_session):
    """A real document's own source_url can only ever be set once, at
    import time -- but a real, live re-derivation must still reflect
    reality (None), not keep serving a stale snapshot forever."""
    org = await _make_org(db_session, "URL Org 4")
    document = await _make_document(db_session, org.id, source_url=None)
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    citation = Citation(
        response_id=response.id, document_id=document.id, text="t", relevance_score=0.9, citation_number=1,
        source_url="https://example.com/stale",
    )
    db_session.add(citation)
    await db_session.commit()

    enriched = await enrich_citation_with_url(db_session, citation)
    assert enriched.source_url is None


async def test_enrich_citations_with_url_enriches_every_real_citation(db_session):
    org = await _make_org(db_session, "URL Org 5")
    document = await _make_document(db_session, org.id, source_url="https://example.com/plural")
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    citations = [Citation(response_id=response.id, document_id=document.id, text="t", relevance_score=0.9, citation_number=1)]
    db_session.add_all(citations)
    await db_session.commit()

    enriched = await enrich_citations_with_url(db_session, citations)
    assert enriched[0].source_url == "https://example.com/plural"


# --------------------------------------- add_citations_to_response now populates source_url --


async def test_add_citations_to_response_populates_real_source_url_from_the_chunk(db_session):
    """Validation criterion: l'URL est capturée à la création de la citation."""
    from api.services.citations import add_citations_to_response

    org = await _make_org(db_session, "URL Org 6")
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    chunks = [{"chunk_id": str(uuid.uuid4()), "document_id": str(uuid.uuid4()), "content": "c", "score": 0.9,
               "document_name": "d.html", "file_type": "text/html", "source_url": "https://example.com/imported"}]

    citations = await add_citations_to_response(db_session, response, chunks)
    await db_session.commit()

    assert citations[0].source_url == "https://example.com/imported"


# --------------------------------------- endpoint --


async def test_citation_endpoint_returns_real_source_url(client, db_session, register_payload):
    """Validation criterion: le lien est cliquable + permissions respectées."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_response = await client.post("/organizations", json={"name": "URL Endpoint Org"}, headers=_auth_header(owner_token))
    org_id = uuid.UUID(org_response.json()["id"])
    document = await _make_document(db_session, org_id, source_url="https://example.com/endpoint")
    response = await _make_response(db_session, org_id)
    await db_session.commit()
    citation = Citation(response_id=response.id, document_id=document.id, text="t", relevance_score=0.9, citation_number=1)
    db_session.add(citation)
    await db_session.commit()

    api_response = await client.get(f"/citations/{citation.id}", headers=_auth_header(owner_token))
    assert api_response.status_code == 200
    assert api_response.json()["source_url"] == "https://example.com/endpoint"

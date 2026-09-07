"""Partie 6.1.2 -- source document (name). Fast SQLite suite."""

import uuid

from sqlalchemy import select

from api.models.citation import Citation
from api.models.document import Document, DocumentStatus
from api.models.organization import Organization, OrganizationMember, OrganizationRole
from api.models.response import Response
from api.models.user import User
from api.services.citation_documents import (
    enrich_citation_with_document, enrich_citations_with_documents, get_document_info,
)


async def _make_org(db_session, name):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


async def _make_document(db_session, org_id, name="report.pdf", file_type="application/pdf"):
    document = Document(
        organization_id=org_id, name=name, file_key=f"documents/{uuid.uuid4()}/{name}",
        file_size=100, file_type=file_type, status=DocumentStatus.completed.value,
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


# --------------------------------------- get_document_info --


async def test_get_document_info_returns_real_name_and_type(db_session):
    """Validation criterion: le nom et le type du document sont affichés."""
    org = await _make_org(db_session, "Doc Info Org")
    document = await _make_document(db_session, org.id, name="quarterly.pdf")
    await db_session.commit()

    info = await get_document_info(db_session, document.id)
    assert info == {"name": "quarterly.pdf", "file_type": "application/pdf"}


async def test_get_document_info_returns_none_for_an_unknown_document(db_session):
    assert await get_document_info(db_session, uuid.uuid4()) is None


async def test_get_document_info_returns_none_for_a_real_soft_deleted_document(db_session):
    """Validation criterion: robustesse -- document supprimé."""
    org = await _make_org(db_session, "Doc Info Org 2")
    document = await _make_document(db_session, org.id)
    await db_session.commit()
    import datetime as dt
    document.deleted_at = dt.datetime.now(dt.timezone.utc)
    await db_session.commit()

    assert await get_document_info(db_session, document.id) is None


# --------------------------------------- enrich_citation_with_document --


async def test_enrich_citation_with_document_refreshes_the_real_live_name(db_session):
    """Validation criterion: cohérence -- le nom vient de la table documents."""
    org = await _make_org(db_session, "Enrich Org")
    document = await _make_document(db_session, org.id, name="original.pdf")
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    citation = Citation(
        response_id=response.id, document_id=document.id, text="cited text", relevance_score=0.9,
        citation_number=1, document_name="stale-name.pdf", document_type="application/pdf",
    )
    db_session.add(citation)
    await db_session.commit()

    # The real document was renamed since this citation was created.
    document.name = "renamed.pdf"
    await db_session.commit()

    enriched = await enrich_citation_with_document(db_session, citation)
    assert enriched.document_name == "renamed.pdf"


async def test_enrich_citation_with_document_keeps_the_real_snapshot_when_the_document_is_gone(db_session):
    """Validation criterion: robustesse -- que se passe-t-il si le document est supprimé."""
    org = await _make_org(db_session, "Enrich Org 2")
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    citation = Citation(
        response_id=response.id, document_id=uuid.uuid4(), text="cited text", relevance_score=0.9,
        citation_number=1, document_name="historical-name.pdf", document_type="application/pdf",
    )
    db_session.add(citation)
    await db_session.commit()

    enriched = await enrich_citation_with_document(db_session, citation)
    assert enriched.document_name == "historical-name.pdf"


async def test_enrich_citation_with_document_is_a_real_no_op_without_a_real_document_id(db_session):
    org = await _make_org(db_session, "Enrich Org 3")
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    citation = Citation(response_id=response.id, document_id=None, text="cited text", relevance_score=0.9, citation_number=1)
    db_session.add(citation)
    await db_session.commit()

    enriched = await enrich_citation_with_document(db_session, citation)
    assert enriched.document_name is None


# --------------------------------------- enrich_citations_with_documents --


async def test_enrich_citations_with_documents_enriches_every_real_citation(db_session):
    org = await _make_org(db_session, "Enrich Org 4")
    document = await _make_document(db_session, org.id, name="live.pdf")
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    citations = [
        Citation(response_id=response.id, document_id=document.id, text="a", relevance_score=0.9, citation_number=1, document_name="stale.pdf"),
        Citation(response_id=response.id, document_id=None, text="b", relevance_score=0.8, citation_number=2),
    ]
    db_session.add_all(citations)
    await db_session.commit()

    enriched = await enrich_citations_with_documents(db_session, citations)
    assert enriched[0].document_name == "live.pdf"
    assert enriched[1].document_name is None


# --------------------------------------- endpoints --


async def test_citation_endpoint_returns_the_real_live_document_name(client, db_session, register_payload):
    """Validation criterion: la récupération fonctionne + permissions respectées."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_response = await client.post("/organizations", json={"name": "Live Name Org"}, headers=_auth_header(owner_token))
    org_id = uuid.UUID(org_response.json()["id"])
    document = await _make_document(db_session, org_id, name="v1.pdf")
    response = await _make_response(db_session, org_id)
    await db_session.commit()
    citation = Citation(
        response_id=response.id, document_id=document.id, text="cited", relevance_score=0.9, citation_number=1,
        document_name="v1.pdf", document_type="application/pdf",
    )
    db_session.add(citation)
    await db_session.commit()
    document.name = "v2.pdf"
    await db_session.commit()

    api_response = await client.get(f"/citations/{citation.id}", headers=_auth_header(owner_token))
    assert api_response.status_code == 200
    assert api_response.json()["document_name"] == "v2.pdf"


async def test_non_member_cannot_read_citation_document_info(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_response = await client.post("/organizations", json={"name": "Doc Isolation Org"}, headers=_auth_header(owner_token))
    org_id = uuid.UUID(org_response.json()["id"])
    response = await _make_response(db_session, org_id)
    await db_session.commit()
    citation = Citation(response_id=response.id, text="cited", relevance_score=0.9, citation_number=1)
    db_session.add(citation)
    await db_session.commit()

    other_token, other = await _register(client, db_session, "other@example.com")
    api_response = await client.get(f"/citations/{citation.id}", headers=_auth_header(other_token))
    assert api_response.status_code == 404

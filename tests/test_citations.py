"""Partie 6.1.1 -- citations. Fast SQLite suite."""

import uuid

import pytest
from sqlalchemy import select

from api.config import settings
from api.models.document import Document, DocumentStatus
from api.models.organization import Organization, OrganizationMember, OrganizationRole
from api.models.response import Response
from api.models.user import User
from api.services.citations import (
    CitationError, add_citations_to_response, format_citation, get_citation_count, get_citations_by_response,
    select_top_citations, validate_citation,
)


async def _make_org(db_session, name):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


async def _make_response(db_session, org_id, answer="The sky is blue [1] and grass is green [2]."):
    response = Response(organization_id=org_id, query="What color is the sky?", answer=answer)
    db_session.add(response)
    await db_session.flush()
    return response


def _make_chunk(score, chunk_id=None, document_id=None, content="Some real content", document_name="doc.pdf", file_type="application/pdf"):
    return {
        "chunk_id": str(chunk_id or uuid.uuid4()), "document_id": str(document_id or uuid.uuid4()),
        "content": content, "score": score, "document_name": document_name, "file_type": file_type,
        "metadata_json": {},
    }


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _add_member(db_session, org_id, user_id, role: OrganizationRole, invited_by=None):
    db_session.add(OrganizationMember(organization_id=org_id, user_id=user_id, role=role, invited_by=invited_by))
    await db_session.commit()


# --------------------------------------- select_top_citations --


def test_select_top_citations_sorts_by_real_score_descending():
    """Validation criterion: la sélection des meilleures citations fonctionne."""
    chunks = [_make_chunk(0.6), _make_chunk(0.9), _make_chunk(0.7)]
    selected = select_top_citations(chunks, 2)
    assert [c["score"] for c in selected] == [0.9, 0.7]


def test_select_top_citations_drops_chunks_below_the_real_min_score(monkeypatch):
    """Validation criterion: robustesse -- pas de remplissage artificiel."""
    monkeypatch.setattr(settings, "CITATION_MIN_SCORE", 0.5)
    chunks = [_make_chunk(0.9), _make_chunk(0.2)]
    selected = select_top_citations(chunks, 5)
    assert len(selected) == 1


def test_select_top_citations_respects_the_real_requested_count():
    chunks = [_make_chunk(0.9), _make_chunk(0.8), _make_chunk(0.7)]
    assert len(select_top_citations(chunks, 2)) == 2


# --------------------------------------- add_citations_to_response --


async def test_add_citations_to_response_creates_5_citations_by_default(db_session):
    """Validation criterion: l'ajout de citations fonctionne (5 citations par défaut)."""
    org = await _make_org(db_session, "Citations Org")
    response = await _make_response(db_session, org.id, answer="Answer with no markers.")
    await db_session.commit()
    chunks = [_make_chunk(0.9 - i * 0.05) for i in range(8)]

    citations = await add_citations_to_response(db_session, response, chunks)
    await db_session.commit()

    assert len(citations) == 5
    assert [c.citation_number for c in citations] == [1, 2, 3, 4, 5]


async def test_add_citations_to_response_links_real_document_and_chunk_ids(db_session):
    """Validation criterion: cohérence -- citations liées aux chunks et documents."""
    org = await _make_org(db_session, "Citations Org 2")
    response = await _make_response(db_session, org.id, answer="No markers here.")
    await db_session.commit()
    doc_id, chunk_id = uuid.uuid4(), uuid.uuid4()
    chunks = [_make_chunk(0.9, chunk_id=chunk_id, document_id=doc_id)]

    citations = await add_citations_to_response(db_session, response, chunks)
    await db_session.commit()

    assert citations[0].document_id == doc_id
    assert citations[0].chunk_id == chunk_id


async def test_add_citations_to_response_finds_real_inline_marker_positions(db_session):
    org = await _make_org(db_session, "Citations Org 3")
    response = await _make_response(db_session, org.id, answer="The sky is blue [1] and grass is green [2].")
    await db_session.commit()
    chunks = [_make_chunk(0.9), _make_chunk(0.8)]

    citations = await add_citations_to_response(db_session, response, chunks)
    await db_session.commit()

    assert response.answer[citations[0].position_start:citations[0].position_end] == "[1]"
    assert response.answer[citations[1].position_start:citations[1].position_end] == "[2]"


async def test_add_citations_to_response_leaves_position_none_when_no_real_marker(db_session):
    """Validation criterion: robustesse -- pas de position fabriquée."""
    org = await _make_org(db_session, "Citations Org 4")
    response = await _make_response(db_session, org.id, answer="An answer with no bracket markers at all.")
    await db_session.commit()
    citations = await add_citations_to_response(db_session, response, [_make_chunk(0.9)])
    await db_session.commit()

    assert citations[0].position_start is None
    assert citations[0].position_end is None


async def test_add_citations_to_response_respects_a_real_custom_count(db_session):
    org = await _make_org(db_session, "Citations Org 5")
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    chunks = [_make_chunk(0.9), _make_chunk(0.8), _make_chunk(0.7)]

    citations = await add_citations_to_response(db_session, response, chunks, citation_count=2)
    await db_session.commit()
    assert len(citations) == 2


# --------------------------------------- format_citation --


def test_format_citation_markdown():
    """Validation criterion: le formatage fonctionne."""
    citation = _fake_citation(source_url="https://example.com")
    formatted = format_citation(citation, "markdown")
    assert formatted == "[1] [My Doc](https://example.com) — Some cited text"


def test_format_citation_html():
    citation = _fake_citation(source_url="https://example.com")
    formatted = format_citation(citation, "html")
    assert '<a href="https://example.com">My Doc</a>' in formatted


def test_format_citation_json():
    citation = _fake_citation()
    formatted = format_citation(citation, "json")
    assert formatted["citation_number"] == 1
    assert formatted["text"] == "Some cited text"


def test_format_citation_rejects_an_unknown_format():
    with pytest.raises(CitationError, match="Unknown format"):
        format_citation(_fake_citation(), "xml")


def _fake_citation(**overrides):
    from api.models.citation import Citation
    defaults = dict(
        id=uuid.uuid4(), response_id=uuid.uuid4(), citation_number=1, text="Some cited text",
        relevance_score=0.9, source_title="My Doc", source_url=None,
    )
    defaults.update(overrides)
    return Citation(**defaults)


# --------------------------------------- get_citations_by_response --


async def test_get_citations_by_response_orders_by_citation_number(db_session):
    """Validation criterion: la récupération fonctionne."""
    org = await _make_org(db_session, "Citations Org 6")
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    await add_citations_to_response(db_session, response, [_make_chunk(0.9), _make_chunk(0.8), _make_chunk(0.7)])
    await db_session.commit()

    citations = await get_citations_by_response(db_session, response.id)
    assert [c.citation_number for c in citations] == [1, 2, 3]


async def test_get_citations_by_response_returns_empty_for_an_unknown_response(db_session):
    assert await get_citations_by_response(db_session, uuid.uuid4()) == []


# --------------------------------------- validate_citation --


def test_validate_citation_accepts_a_real_valid_citation():
    validate_citation(_fake_citation())


def test_validate_citation_rejects_a_non_positive_citation_number():
    with pytest.raises(CitationError, match="citation_number"):
        validate_citation(_fake_citation(citation_number=0))


def test_validate_citation_rejects_an_out_of_range_score():
    with pytest.raises(CitationError, match="relevance_score"):
        validate_citation(_fake_citation(relevance_score=1.5))


def test_validate_citation_rejects_empty_text():
    with pytest.raises(CitationError, match="non-empty text"):
        validate_citation(_fake_citation(text=""))


# --------------------------------------- get_citation_count --


async def test_get_citation_count_returns_the_real_default(db_session):
    """Validation criterion: la configuration du nombre de citations fonctionne."""
    org = await _make_org(db_session, "Citations Org 7")
    await db_session.commit()
    assert await get_citation_count(db_session, org.id) == settings.CITATION_DEFAULT_COUNT


async def test_get_citation_count_respects_a_real_org_override(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_response = await client.post("/organizations", json={"name": "Citation Count Org"}, headers=_auth_header(owner_token))
    org_id = uuid.UUID(org_response.json()["id"])
    await client.patch(f"/organizations/{org_id}/settings", json={"citation_count": 8}, headers=_auth_header(owner_token))

    assert await get_citation_count(db_session, org_id) == 8


async def test_get_citation_count_is_capped_at_the_real_max(db_session, monkeypatch):
    monkeypatch.setattr(settings, "CITATION_MAX_COUNT", 10)
    org = await _make_org(db_session, "Citations Org 8")
    await db_session.commit()

    async def _fake_org_settings(db, organization_id):
        return {"citation_count": 999}

    monkeypatch.setattr("api.services.citations.get_org_settings", _fake_org_settings)
    assert await get_citation_count(db_session, org.id) == 10


# --------------------------------------- endpoints --


async def test_member_can_list_citations_by_response(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_response = await client.post("/organizations", json={"name": "Citation Endpoint Org"}, headers=_auth_header(owner_token))
    org_id = uuid.UUID(org_response.json()["id"])
    response = await _make_response(db_session, org_id)
    await db_session.commit()
    await add_citations_to_response(db_session, response, [_make_chunk(0.9)])
    await db_session.commit()

    list_response = await client.get(f"/responses/{response.id}/citations", headers=_auth_header(owner_token))
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    citation_id = list_response.json()[0]["id"]
    get_response = await client.get(f"/citations/{citation_id}", headers=_auth_header(owner_token))
    assert get_response.status_code == 200


async def test_non_member_cannot_access_citations(client, db_session, register_payload):
    """Validation criterion: sécurité -- les permissions sont respectées."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_response = await client.post("/organizations", json={"name": "Citation Isolation Org"}, headers=_auth_header(owner_token))
    org_id = uuid.UUID(org_response.json()["id"])
    response = await _make_response(db_session, org_id)
    await db_session.commit()

    other_token, other = await _register(client, db_session, "other@example.com")
    get_response = await client.get(f"/responses/{response.id}/citations", headers=_auth_header(other_token))
    assert get_response.status_code == 404


async def test_member_can_list_citations_by_document(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_response = await client.post("/organizations", json={"name": "Doc Citation Org"}, headers=_auth_header(owner_token))
    org_id = uuid.UUID(org_response.json()["id"])
    document = Document(
        organization_id=org_id, name="real.pdf", file_key=f"documents/{uuid.uuid4()}/real.pdf",
        file_size=10, file_type="application/pdf", status=DocumentStatus.completed.value,
    )
    db_session.add(document)
    await db_session.flush()
    response = await _make_response(db_session, org_id)
    await db_session.commit()
    await add_citations_to_response(db_session, response, [_make_chunk(0.9, document_id=document.id)])
    await db_session.commit()

    list_response = await client.get(f"/documents/{document.id}/citations", headers=_auth_header(owner_token))
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

"""Partie 6.1.7 -- passage exact. Fast SQLite suite."""

import uuid

from sqlalchemy import select

from api.models.citation import Citation
from api.models.document import Document, DocumentChunk, DocumentStatus
from api.models.organization import Organization
from api.models.response import Response
from api.models.user import User
from api.services.citation_passage import (
    enrich_citation_with_passage, enrich_citations_with_passage, extract_passage_from_chunk,
    format_passage_preview, get_passage_context, highlight_passage,
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


# --------------------------------------- extract_passage_from_chunk --


def test_extract_passage_from_chunk_returns_the_whole_real_content_by_default():
    """Validation criterion: le passage exact est extrait."""
    assert extract_passage_from_chunk({"content": "the full real chunk content"}) == "the full real chunk content"


def test_extract_passage_from_chunk_slices_a_real_explicit_span():
    assert extract_passage_from_chunk({"content": "0123456789"}, position_start=2, position_end=5) == "234"


def test_extract_passage_from_chunk_clamps_out_of_range_positions():
    """Validation criterion: robustesse -- positions invalides."""
    assert extract_passage_from_chunk({"content": "0123456789"}, position_start=-5, position_end=999) == "0123456789"


def test_extract_passage_from_chunk_accepts_a_real_orm_object_too():
    class _FakeChunk:
        content = "abcdef"

    assert extract_passage_from_chunk(_FakeChunk(), position_start=1, position_end=3) == "bc"


# --------------------------------------- format_passage_preview --


def test_format_passage_preview_returns_short_text_unchanged():
    """Validation criterion: l'aperçu est lisible et court."""
    assert format_passage_preview("short text", max_length=200) == "short text"


def test_format_passage_preview_truncates_long_text_honestly():
    text = "x" * 300
    preview = format_passage_preview(text, max_length=200)
    assert len(preview) == 201
    assert preview.endswith("…")


# --------------------------------------- highlight_passage --


def test_highlight_passage_wraps_real_matches_case_insensitively():
    """Validation criterion: les termes recherchés sont mis en évidence."""
    assert highlight_passage("The Quick Brown Fox", ["quick", "fox"]) == "The **Quick** Brown **Fox**"


def test_highlight_passage_is_a_real_no_op_for_empty_search_terms():
    assert highlight_passage("unchanged text", []) == "unchanged text"


def test_highlight_passage_escapes_real_regex_special_characters():
    """Validation criterion: robustesse -- un terme de recherche n'est jamais interprété comme un motif."""
    assert highlight_passage("cost: $5.00 (tax incl.)", ["$5.00"]) == "cost: **$5.00** (tax incl.)"


# --------------------------------------- enrich_citation_with_passage --


async def test_enrich_citation_with_passage_refreshes_from_the_real_live_chunk(db_session):
    """Validation criterion: cohérence -- l'aperçu vient du vrai chunk."""
    org = await _make_org(db_session, "Passage Org")
    document = await _make_document(db_session, org.id)
    chunk = await _make_chunk(db_session, document, org.id, content="the real, current chunk content")
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    citation = Citation(
        response_id=response.id, document_id=document.id, chunk_id=chunk.id, text="stale text", relevance_score=0.9,
        citation_number=1,
    )
    db_session.add(citation)
    await db_session.commit()

    enriched = await enrich_citation_with_passage(db_session, citation)
    assert enriched.text_preview == "the real, current chunk content"


async def test_enrich_citation_with_passage_falls_back_to_the_real_snapshot_text_without_a_chunk_id(db_session):
    org = await _make_org(db_session, "Passage Org 2")
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    citation = Citation(response_id=response.id, chunk_id=None, text="the real snapshot text", relevance_score=0.9, citation_number=1)
    db_session.add(citation)
    await db_session.commit()

    enriched = await enrich_citation_with_passage(db_session, citation)
    assert enriched.text_preview == "the real snapshot text"


async def test_enrich_citation_with_passage_keeps_the_real_snapshot_when_the_chunk_is_gone(db_session):
    """Validation criterion: robustesse -- chunk supprimé."""
    org = await _make_org(db_session, "Passage Org 3")
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    citation = Citation(
        response_id=response.id, chunk_id=uuid.uuid4(), text="t", relevance_score=0.9, citation_number=1,
        text_preview="historical preview",
    )
    db_session.add(citation)
    await db_session.commit()

    enriched = await enrich_citation_with_passage(db_session, citation)
    assert enriched.text_preview == "historical preview"


async def test_enrich_citations_with_passage_enriches_every_real_citation(db_session):
    org = await _make_org(db_session, "Passage Org 4")
    document = await _make_document(db_session, org.id)
    chunk = await _make_chunk(db_session, document, org.id, content="live content")
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    citations = [
        Citation(response_id=response.id, document_id=document.id, chunk_id=chunk.id, text="t", relevance_score=0.9, citation_number=1),
    ]
    db_session.add_all(citations)
    await db_session.commit()

    enriched = await enrich_citations_with_passage(db_session, citations)
    assert enriched[0].text_preview == "live content"


# --------------------------------------- add_citations_to_response now populates text_preview --


async def test_add_citations_to_response_populates_real_text_preview(db_session):
    """Validation criterion: l'aperçu est capturé à la création de la citation."""
    from api.services.citations import add_citations_to_response

    org = await _make_org(db_session, "Passage Org 5")
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    chunks = [{"chunk_id": str(uuid.uuid4()), "document_id": str(uuid.uuid4()), "content": "the exact quoted passage",
               "score": 0.9, "document_name": "d.pdf", "file_type": "pdf"}]

    citations = await add_citations_to_response(db_session, response, chunks)
    await db_session.commit()

    assert citations[0].text_preview == "the exact quoted passage"


# --------------------------------------- get_passage_context --


async def test_get_passage_context_reads_real_adjacent_sibling_chunks(db_session):
    """Validation criterion: le contexte autour du passage est fourni."""
    org = await _make_org(db_session, "Passage Context Org")
    document = await _make_document(db_session, org.id)
    await _make_chunk(db_session, document, org.id, content="before words here end", chunk_index=1)
    middle = await _make_chunk(db_session, document, org.id, content="the cited passage", chunk_index=2)
    await _make_chunk(db_session, document, org.id, content="after words start here", chunk_index=3)
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    citation = Citation(
        response_id=response.id, document_id=document.id, chunk_id=middle.id, chunk_index=2, text="the cited passage",
        relevance_score=0.9, citation_number=1,
    )
    db_session.add(citation)
    await db_session.commit()

    context = await get_passage_context(db_session, citation, context_words=3)
    assert context == {"before": "words here end", "after": "after words start"}


async def test_get_passage_context_is_honestly_empty_at_the_real_start_of_a_document(db_session):
    """Validation criterion: robustesse -- début/fin de document."""
    org = await _make_org(db_session, "Passage Context Org 2")
    document = await _make_document(db_session, org.id)
    first = await _make_chunk(db_session, document, org.id, content="the very first chunk", chunk_index=1)
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    citation = Citation(
        response_id=response.id, document_id=document.id, chunk_id=first.id, chunk_index=1, text="t",
        relevance_score=0.9, citation_number=1,
    )
    db_session.add(citation)
    await db_session.commit()

    context = await get_passage_context(db_session, citation, context_words=3)
    assert context == {"before": "", "after": ""}


async def test_get_passage_context_is_honestly_empty_without_a_real_chunk_index(db_session):
    org = await _make_org(db_session, "Passage Context Org 3")
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    citation = Citation(response_id=response.id, text="t", relevance_score=0.9, citation_number=1)
    db_session.add(citation)
    await db_session.commit()

    context = await get_passage_context(db_session, citation, context_words=3)
    assert context == {"before": "", "after": ""}


# --------------------------------------- endpoint --


async def test_citation_endpoint_returns_real_text_preview(client, db_session, register_payload):
    """Validation criterion: la récupération fonctionne + permissions respectées."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_response = await client.post("/organizations", json={"name": "Passage Endpoint Org"}, headers=_auth_header(owner_token))
    org_id = uuid.UUID(org_response.json()["id"])
    document = await _make_document(db_session, org_id)
    chunk = await _make_chunk(db_session, document, org_id, content="the real endpoint content")
    response = await _make_response(db_session, org_id)
    await db_session.commit()
    citation = Citation(
        response_id=response.id, document_id=document.id, chunk_id=chunk.id, text="t", relevance_score=0.9, citation_number=1,
    )
    db_session.add(citation)
    await db_session.commit()

    api_response = await client.get(f"/citations/{citation.id}", headers=_auth_header(owner_token))
    assert api_response.status_code == 200
    assert api_response.json()["text_preview"] == "the real endpoint content"

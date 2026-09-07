"""Partie 6.1.8 -- citation preview / hover. Fast SQLite suite."""

import uuid

from api.config import settings
from api.models.citation import Citation
from api.models.document import Document, DocumentChunk, DocumentStatus
from api.models.organization import Organization
from api.models.response import Response
from api.services.citation_preview import (
    enrich_citation_with_preview, format_citation_preview, get_citation_context, get_citation_preview,
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


# --------------------------------------- format_citation_preview --


def test_format_citation_preview_uses_the_real_configured_default_length():
    """Validation criterion: l'aperçu au survol est lisible et court."""
    citation = Citation(response_id=uuid.uuid4(), text="x" * 300, relevance_score=0.9, citation_number=1)
    preview = format_citation_preview(citation)
    assert len(preview) == settings.CITATION_PREVIEW_LENGTH + 1
    assert preview.endswith("…")


def test_format_citation_preview_honors_a_real_explicit_length():
    citation = Citation(response_id=uuid.uuid4(), text="0123456789", relevance_score=0.9, citation_number=1)
    assert format_citation_preview(citation, preview_length=5) == "01234…"


def test_format_citation_preview_returns_short_text_unchanged():
    citation = Citation(response_id=uuid.uuid4(), text="short", relevance_score=0.9, citation_number=1)
    assert format_citation_preview(citation) == "short"


# --------------------------------------- enrich_citation_with_preview --


def test_enrich_citation_with_preview_sets_the_real_shared_text_preview_field():
    """Validation criterion: cohérence -- réutilise le même champ que la Partie 6.1.7."""
    citation = Citation(response_id=uuid.uuid4(), text="0123456789", relevance_score=0.9, citation_number=1)
    enriched = enrich_citation_with_preview(citation, preview_length=5)
    assert enriched.text_preview == "01234…"


# --------------------------------------- get_citation_preview --


async def test_get_citation_preview_reads_the_real_live_citation(db_session):
    """Validation criterion: le survol fonctionne sur une vraie citation."""
    org = await _make_org(db_session, "Preview Org")
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    citation = Citation(response_id=response.id, text="0123456789", relevance_score=0.9, citation_number=1)
    db_session.add(citation)
    await db_session.commit()

    assert await get_citation_preview(db_session, citation.id, preview_length=5) == "01234…"


async def test_get_citation_preview_returns_none_for_an_unknown_citation(db_session):
    """Validation criterion: robustesse -- citation introuvable."""
    assert await get_citation_preview(db_session, uuid.uuid4()) is None


# --------------------------------------- get_citation_context --


async def test_get_citation_context_delegates_to_the_real_partie_6_1_7_logic(db_session):
    """Validation criterion: cohérence -- pas de logique dupliquée avec la Partie 6.1.7."""
    org = await _make_org(db_session, "Preview Context Org")
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

    context = await get_citation_context(db_session, citation.id, context_words=3)
    assert context == {"before": "words here end", "after": "after words start"}


async def test_get_citation_context_returns_none_for_an_unknown_citation(db_session):
    assert await get_citation_context(db_session, uuid.uuid4()) is None

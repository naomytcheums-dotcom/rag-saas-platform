"""Partie 6.1.9 -- sources secondaires. Fast SQLite suite."""

import uuid

from api.config import settings
from api.models.citation import Citation
from api.models.organization import Organization
from api.models.response import Response
from api.services.citation_secondary import (
    format_secondary_sources, get_secondary_source_count, get_sources_by_response, select_primary_sources,
    select_secondary_sources,
)
from api.services.citations import add_citations_to_response


def _make_chunk(score, chunk_id=None, document_id=None, content="Some real content", document_name="doc.pdf"):
    return {
        "chunk_id": str(chunk_id or uuid.uuid4()), "document_id": str(document_id or uuid.uuid4()),
        "content": content, "score": score, "document_name": document_name, "file_type": "application/pdf",
    }


async def _make_org(db_session, name):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


async def _make_response(db_session, org_id, answer="An answer."):
    response = Response(organization_id=org_id, query="q", answer=answer)
    db_session.add(response)
    await db_session.flush()
    return response


# --------------------------------------- select_primary_sources --


def test_select_primary_sources_is_the_real_same_logic_as_select_top_citations():
    """Validation criterion: les sources primaires sont sélectionnées correctement."""
    chunks = [_make_chunk(0.9), _make_chunk(0.6), _make_chunk(0.2)]
    selected = select_primary_sources(chunks, 5)
    assert [c["score"] for c in selected] == [0.9, 0.6]


# --------------------------------------- select_secondary_sources --


def test_select_secondary_sources_selects_the_real_band_below_min_score():
    """Validation criterion: les sources secondaires (moins pertinentes) sont identifiées."""
    chunks = [_make_chunk(0.9), _make_chunk(0.45), _make_chunk(0.35), _make_chunk(0.1)]
    selected = select_secondary_sources(chunks, 5, settings.CITATION_SECONDARY_THRESHOLD)
    assert [c["score"] for c in selected] == [0.45, 0.35]


def test_select_secondary_sources_respects_the_real_requested_count():
    chunks = [_make_chunk(0.49), _make_chunk(0.48), _make_chunk(0.47)]
    selected = select_secondary_sources(chunks, 2, 0.3)
    assert len(selected) == 2


def test_select_secondary_sources_is_honestly_empty_below_the_real_threshold():
    """Validation criterion: robustesse -- rien en dessous du seuil."""
    chunks = [_make_chunk(0.2), _make_chunk(0.1)]
    assert select_secondary_sources(chunks, 5, 0.3) == []


# --------------------------------------- add_citations_to_response now persists secondary citations --


async def test_add_citations_to_response_persists_real_secondary_citations(db_session, monkeypatch):
    """Validation criterion: les sources secondaires sont bien liées à la réponse."""
    monkeypatch.setattr(settings, "CITATION_SECONDARY_ENABLED", True)
    org = await _make_org(db_session, "Secondary Org")
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    chunks = [_make_chunk(0.9), _make_chunk(0.85), _make_chunk(0.45), _make_chunk(0.4)]

    citations = await add_citations_to_response(db_session, response, chunks, citation_count=2)
    await db_session.commit()

    primary = [c for c in citations if c.is_primary]
    secondary = [c for c in citations if not c.is_primary]
    assert [round(c.relevance_score, 2) for c in primary] == [0.9, 0.85]
    assert [round(c.relevance_score, 2) for c in secondary] == [0.45, 0.4]
    # Partie 6.1.9's own note in citations.py's own _build_citation --
    # secondary citations continue the SAME real citation_number
    # sequence, never re-using a primary citation's own number.
    assert [c.citation_number for c in citations] == [1, 2, 3, 4]


async def test_add_citations_to_response_never_persists_secondary_citations_when_disabled(db_session, monkeypatch):
    monkeypatch.setattr(settings, "CITATION_SECONDARY_ENABLED", False)
    org = await _make_org(db_session, "Secondary Org 2")
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    chunks = [_make_chunk(0.9), _make_chunk(0.45)]

    citations = await add_citations_to_response(db_session, response, chunks)
    await db_session.commit()

    assert len(citations) == 1
    assert citations[0].is_primary is True


# --------------------------------------- get_sources_by_response --


async def test_get_sources_by_response_includes_secondary_by_default(db_session, monkeypatch):
    """Validation criterion: la récupération distingue sources primaires et secondaires."""
    monkeypatch.setattr(settings, "CITATION_SECONDARY_ENABLED", True)
    org = await _make_org(db_session, "Secondary Org 3")
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    await add_citations_to_response(db_session, response, [_make_chunk(0.9), _make_chunk(0.45)], citation_count=1)
    await db_session.commit()

    all_sources = await get_sources_by_response(db_session, response.id, include_secondary=True)
    primary_only = await get_sources_by_response(db_session, response.id, include_secondary=False)
    assert len(all_sources) == 2
    assert len(primary_only) == 1
    assert primary_only[0].is_primary is True


async def test_get_sources_by_response_returns_empty_for_an_unknown_response(db_session):
    assert await get_sources_by_response(db_session, uuid.uuid4()) == []


# --------------------------------------- get_secondary_source_count --


async def test_get_secondary_source_count_counts_only_real_secondary_citations(db_session, monkeypatch):
    """Validation criterion: le nombre de sources secondaires est correct."""
    monkeypatch.setattr(settings, "CITATION_SECONDARY_ENABLED", True)
    org = await _make_org(db_session, "Secondary Org 4")
    response = await _make_response(db_session, org.id)
    await db_session.commit()
    await add_citations_to_response(db_session, response, [_make_chunk(0.9), _make_chunk(0.45), _make_chunk(0.4)], citation_count=1)
    await db_session.commit()

    assert await get_secondary_source_count(db_session, response.id) == 2


async def test_get_secondary_source_count_is_zero_for_an_unknown_response(db_session):
    assert await get_secondary_source_count(db_session, uuid.uuid4()) == 0


# --------------------------------------- format_secondary_sources --


def test_format_secondary_sources_renders_a_real_markdown_list():
    """Validation criterion: le formatage des sources secondaires fonctionne."""
    sources = [
        Citation(
            response_id=uuid.uuid4(), text="t", relevance_score=0.4, citation_number=2, is_primary=False,
            source_title="Doc A", source_url="https://example.com/a",
        ),
        Citation(response_id=uuid.uuid4(), text="t", relevance_score=0.35, citation_number=3, is_primary=False, source_title="Doc B"),
    ]
    formatted = format_secondary_sources(sources)
    assert formatted == "- [Doc A](https://example.com/a)\n- Doc B"


def test_format_secondary_sources_is_honestly_empty_for_no_real_sources():
    assert format_secondary_sources([]) == ""

"""Partie 6.2.8 -- source consistency check. Fast SQLite suite."""

import datetime as dt
import uuid

from api.config import settings
from api.models.citation import Citation
from api.models.document import Document, DocumentStatus
from api.models.organization import Organization
from api.services.source_consistency import (
    calculate_source_agreement, check_source_consistency, compare_source_claims, group_sources_by_topic,
    identify_source_conflicts,
)


def _citation(text, number=1, document_id=None, is_primary=True):
    return Citation(
        response_id=uuid.uuid4(), text=text, relevance_score=0.9, citation_number=number, document_id=document_id,
        is_primary=is_primary,
    )


async def _make_org(db_session, name):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


async def _make_document(db_session, org_id, name="doc.pdf", processed_at=None):
    document = Document(
        organization_id=org_id, name=name, file_key=f"documents/{uuid.uuid4()}/{name}",
        file_size=10, file_type="application/pdf", status=DocumentStatus.completed.value, processed_at=processed_at,
    )
    db_session.add(document)
    await db_session.flush()
    return document


# --------------------------------------- group_sources_by_topic --


def test_group_sources_by_topic_groups_real_overlapping_sources():
    """Validation criterion: la vérification de cohérence fonctionne."""
    citations = [
        _citation("The clinical study included 500 participants total.", number=1),
        _citation("The clinical study included 500 participants in total.", number=2),
        _citation("Bananas are a good source of potassium.", number=3),
    ]
    groups = group_sources_by_topic(citations)
    assert len(groups) == 2
    assert {c.citation_number for c in groups[0]} == {1, 2} or {c.citation_number for c in groups[1]} == {1, 2}


# --------------------------------------- compare_source_claims / calculate_source_agreement --


def test_compare_source_claims_flags_a_real_conflicting_pair():
    citations = [
        _citation("The clinical study included exactly 500 participants total in 2020 and was published in a peer reviewed journal.", number=1),
        _citation("The clinical study included exactly 800 participants total in 2020 and was published in a peer reviewed journal.", number=2),
    ]
    comparisons = compare_source_claims(citations)
    assert len(comparisons) == 1
    assert comparisons[0]["agrees"] is False


def test_calculate_source_agreement_is_honestly_perfect_with_nothing_to_compare():
    """Validation criterion: robustesse -- une seule source."""
    assert calculate_source_agreement([_citation("A lone citation.")]) == 1.0
    assert calculate_source_agreement([]) == 1.0


def test_calculate_source_agreement_reflects_real_conflicting_sources():
    citations = [
        _citation("The clinical study included exactly 500 participants total in 2020 and was published in a peer reviewed journal.", number=1),
        _citation("The clinical study included exactly 800 participants total in 2020 and was published in a peer reviewed journal.", number=2),
    ]
    assert calculate_source_agreement(citations) == 0.0


def test_identify_source_conflicts_lists_the_real_conflicting_pair():
    """Validation criterion: les conflits sont détectés."""
    citations = [
        _citation("The clinical study included exactly 500 participants total in 2020 and was published in a peer reviewed journal.", number=1),
        _citation("The clinical study included exactly 800 participants total in 2020 and was published in a peer reviewed journal.", number=2),
    ]
    conflicts = identify_source_conflicts(citations)
    assert len(conflicts) == 1
    assert conflicts[0]["conflict"]["type"] == "factual"


# --------------------------------------- check_source_consistency --


async def test_check_source_consistency_reflects_real_conflicting_sources(db_session):
    """Validation criterion: le score de cohérence est correct."""
    org = await _make_org(db_session, "Consistency Org")
    doc_a = await _make_document(db_session, org.id, name="a.pdf")
    doc_b = await _make_document(db_session, org.id, name="b.pdf")
    citations = [
        _citation("The clinical study included exactly 500 participants total in 2020 and was published in a peer reviewed journal.", number=1, document_id=doc_a.id),
        _citation("The clinical study included exactly 800 participants total in 2020 and was published in a peer reviewed journal.", number=2, document_id=doc_b.id),
    ]
    await db_session.commit()

    result = await check_source_consistency(db_session, citations)
    assert result["agreement_score"] == 0.0
    assert result["conflict_count"] == 1
    assert result["source_diversity"] == 1.0


async def test_check_source_consistency_is_honest_below_the_real_minimum_source_count(db_session):
    """Validation criterion: robustesse -- pas assez de sources pour comparer."""
    result = await check_source_consistency(db_session, [_citation("A lone citation.")])
    assert result["agreement_score"] == 1.0
    assert result["conflict_count"] == 0


async def test_check_source_consistency_is_a_real_no_op_when_disabled(db_session, monkeypatch):
    monkeypatch.setattr(settings, "SOURCE_CONSISTENCY_ENABLED", False)
    result = await check_source_consistency(db_session, [_citation("Some text.", number=1), _citation("Other text.", number=2)])
    assert result == {
        "agreement_score": 1.0, "conflict_count": 0, "source_diversity": 0.0,
        "source_reliability": 0.0, "temporal_consistency": 1.0,
    }


async def test_check_source_consistency_temporal_consistency_drops_for_real_distant_dates(db_session):
    """Validation criterion: les métriques de cohérence sont correctes (temporal_consistency)."""
    org = await _make_org(db_session, "Temporal Org")
    now = dt.datetime.now(dt.timezone.utc)
    doc_recent_a = await _make_document(db_session, org.id, name="recent-a.pdf", processed_at=now)
    doc_recent_b = await _make_document(db_session, org.id, name="recent-b.pdf", processed_at=now)
    doc_old = await _make_document(db_session, org.id, name="old.pdf", processed_at=now - dt.timedelta(days=800))

    recent_citations = [
        _citation("Some real content A.", number=1, document_id=doc_recent_a.id),
        _citation("Some real content B.", number=2, document_id=doc_recent_b.id),
    ]
    spread_out_citations = recent_citations + [_citation("Some old content.", number=3, document_id=doc_old.id)]
    await db_session.commit()

    recent_result = await check_source_consistency(db_session, recent_citations)
    spread_result = await check_source_consistency(db_session, spread_out_citations)
    assert recent_result["temporal_consistency"] == 1.0
    assert spread_result["temporal_consistency"] < recent_result["temporal_consistency"]

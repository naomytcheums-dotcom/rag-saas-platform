"""Partie 7.3.10 -- production A/B testing. Fast, pure-DB suite (no
real LLM calls at all -- traffic-split bucketing and metric tracking
are pure Python/DB logic)."""

import uuid

import pytest

from api.models.evaluation import ABTestStatus
from api.models.organization import Organization
from api.services.ab_tests import (
    complete_ab_test, create_ab_test, get_ab_test_results, get_ab_test_variant, list_ab_tests, pause_ab_test,
    start_ab_test, track_ab_test_metric,
)


async def _make_org(db_session, name):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


async def test_create_ab_test_starts_as_draft(db_session):
    """Validation criterion: la création de test fonctionne."""
    org = await _make_org(db_session, "AB Test Org")
    await db_session.commit()

    test = await create_ab_test(db_session, org.id, "Prompt A vs B", {"system_prompt": "A"}, {"system_prompt": "B"})
    await db_session.commit()

    assert test.status == ABTestStatus.draft
    assert test.traffic_split == 50


async def test_create_ab_test_rejects_an_invalid_traffic_split(db_session):
    """Validation criterion: robustesse."""
    org = await _make_org(db_session, "AB Test Bad Split Org")
    await db_session.commit()
    with pytest.raises(ValueError):
        await create_ab_test(db_session, org.id, "Bad", {}, {}, traffic_split=150)


async def test_start_ab_test_works(db_session):
    """Validation criterion: le démarrage fonctionne."""
    org = await _make_org(db_session, "AB Test Start Org")
    await db_session.commit()
    test = await create_ab_test(db_session, org.id, "T", {}, {})
    await db_session.commit()

    started = await start_ab_test(db_session, test.id)
    await db_session.commit()
    assert started.status == ABTestStatus.running
    assert started.start_date is not None


async def test_pause_and_complete_ab_test_work(db_session):
    org = await _make_org(db_session, "AB Test Pause Org")
    await db_session.commit()
    test = await create_ab_test(db_session, org.id, "T", {}, {})
    await db_session.commit()
    await start_ab_test(db_session, test.id)
    await db_session.commit()

    paused = await pause_ab_test(db_session, test.id)
    await db_session.commit()
    assert paused.status == ABTestStatus.paused

    completed = await complete_ab_test(db_session, test.id)
    await db_session.commit()
    assert completed.status == ABTestStatus.completed
    assert completed.end_date is not None


async def test_get_ab_test_variant_is_deterministic_and_sticky(db_session):
    """Validation criterion: le routage des variants est rapide et cohérent."""
    org = await _make_org(db_session, "AB Test Variant Org")
    await db_session.commit()
    test = await create_ab_test(db_session, org.id, "T", {}, {}, traffic_split=50)
    await db_session.commit()
    started = await start_ab_test(db_session, test.id)
    await db_session.commit()

    first = get_ab_test_variant(started, "user-123")
    second = get_ab_test_variant(started, "user-123")
    assert first == second
    assert first in ("a", "b")


async def test_get_ab_test_variant_defaults_to_a_for_a_non_running_test(db_session):
    """Validation criterion: robustesse -- un variant échoue/n'est pas actif."""
    org = await _make_org(db_session, "AB Test Draft Org")
    await db_session.commit()
    test = await create_ab_test(db_session, org.id, "T", {}, {})
    await db_session.commit()

    assert get_ab_test_variant(test, "any-user") == "a"


async def test_get_ab_test_variant_splits_roughly_by_traffic_split(db_session):
    org = await _make_org(db_session, "AB Test Split Org")
    await db_session.commit()
    test = await create_ab_test(db_session, org.id, "T", {}, {}, traffic_split=100)
    await db_session.commit()
    started = await start_ab_test(db_session, test.id)
    await db_session.commit()

    variants = {get_ab_test_variant(started, f"user-{i}") for i in range(20)}
    assert variants == {"a"}  # traffic_split=100 -- every real user goes to A


async def test_track_ab_test_metric_accumulates_real_running_stats(db_session):
    """Validation criterion: l'enregistrement des métriques fonctionne."""
    org = await _make_org(db_session, "AB Test Track Org")
    await db_session.commit()
    test = await create_ab_test(db_session, org.id, "T", {}, {})
    await db_session.commit()

    await track_ab_test_metric(db_session, test.id, "a", "conversion_rate", 1.0)
    updated = await track_ab_test_metric(db_session, test.id, "a", "conversion_rate", 0.0)
    await db_session.commit()

    stats = updated.metrics["a"]["conversion_rate"]
    assert stats["count"] == 2
    assert stats["sum"] == 1.0


async def test_track_ab_test_metric_rejects_an_invalid_variant(db_session):
    """Validation criterion: robustesse."""
    org = await _make_org(db_session, "AB Test Bad Variant Org")
    await db_session.commit()
    test = await create_ab_test(db_session, org.id, "T", {}, {})
    await db_session.commit()

    with pytest.raises(ValueError):
        await track_ab_test_metric(db_session, test.id, "c", "conversion_rate", 1.0)


async def test_track_ab_test_metric_is_honestly_none_for_an_unknown_test(db_session):
    """Validation criterion: robustesse."""
    assert await track_ab_test_metric(db_session, uuid.uuid4(), "a", "conversion_rate", 1.0) is None


async def test_get_ab_test_results_flags_a_real_significant_difference(db_session):
    """Validation criterion: les résultats sont corrects, statistiquement significatifs."""
    org = await _make_org(db_session, "AB Test Results Org")
    await db_session.commit()
    test = await create_ab_test(db_session, org.id, "T", {}, {})
    await db_session.commit()

    for _ in range(50):
        await track_ab_test_metric(db_session, test.id, "a", "conversion_rate", 0.0)
    for _ in range(50):
        await track_ab_test_metric(db_session, test.id, "b", "conversion_rate", 1.0)
    await db_session.commit()

    results = await get_ab_test_results(db_session, test.id)
    metric = results["metrics"]["conversion_rate"]
    assert metric["variant_a"]["mean"] == 0.0
    assert metric["variant_b"]["mean"] == 1.0
    assert metric["significant"] is True


async def test_get_ab_test_results_honestly_reports_no_real_significance_with_insufficient_samples(db_session):
    """Validation criterion: robustesse."""
    org = await _make_org(db_session, "AB Test Thin Org")
    await db_session.commit()
    test = await create_ab_test(db_session, org.id, "T", {}, {})
    await db_session.commit()
    await track_ab_test_metric(db_session, test.id, "a", "conversion_rate", 1.0)
    await track_ab_test_metric(db_session, test.id, "b", "conversion_rate", 0.0)
    await db_session.commit()

    results = await get_ab_test_results(db_session, test.id)
    assert results["metrics"]["conversion_rate"]["significant"] is None


async def test_get_ab_test_results_is_honestly_none_for_an_unknown_test(db_session):
    """Validation criterion: robustesse."""
    assert await get_ab_test_results(db_session, uuid.uuid4()) is None


async def test_list_ab_tests_paginates(db_session):
    org = await _make_org(db_session, "AB Test List Org")
    await db_session.commit()
    for i in range(3):
        await create_ab_test(db_session, org.id, f"T{i}", {}, {})
    await db_session.commit()

    page = await list_ab_tests(db_session, org.id, limit=2, offset=0)
    assert page["total"] == 3
    assert len(page["items"]) == 2

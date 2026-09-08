"""Partie 7.3.9 -- regression thresholds. Fast, pure-DB suite."""

import uuid

from api.models.organization import Organization
from api.services.regression_thresholds import (
    check_regression_thresholds, delete_regression_threshold, get_regression_threshold, get_regression_thresholds,
    set_regression_threshold, update_regression_threshold,
)


async def _make_org(db_session, name):
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


async def test_set_regression_threshold_creates_a_real_row(db_session):
    """Validation criterion: la création de seuil fonctionne."""
    org = await _make_org(db_session, "Threshold Org")
    await db_session.commit()

    threshold = await set_regression_threshold(db_session, org.id, "faithfulness", 0.7, "high")
    await db_session.commit()

    assert threshold.metric == "faithfulness"
    assert threshold.threshold == 0.7
    assert threshold.enabled is True


async def test_set_regression_threshold_upserts_the_real_existing_row(db_session):
    """Validation criterion: les modifications fonctionnent."""
    org = await _make_org(db_session, "Threshold Upsert Org")
    await db_session.commit()
    await set_regression_threshold(db_session, org.id, "faithfulness", 0.7, "high")
    await db_session.commit()

    updated = await set_regression_threshold(db_session, org.id, "faithfulness", 0.8, "critical")
    await db_session.commit()

    rows = await get_regression_thresholds(db_session, org.id)
    assert len(rows) == 1
    assert rows[0].threshold == 0.8
    assert rows[0].severity == "critical"


async def test_check_regression_thresholds_flags_a_real_higher_is_better_violation(db_session):
    """Validation criterion: la vérification fonctionne."""
    org = await _make_org(db_session, "Threshold Check Org")
    await db_session.commit()
    await set_regression_threshold(db_session, org.id, "faithfulness", 0.7, "high")
    await db_session.commit()

    violations = await check_regression_thresholds(db_session, org.id, {"faithfulness": 0.5})
    assert len(violations) == 1
    assert violations[0]["metric"] == "faithfulness"


async def test_check_regression_thresholds_flags_a_real_lower_is_better_violation(db_session):
    org = await _make_org(db_session, "Threshold Check Lower Org")
    await db_session.commit()
    await set_regression_threshold(db_session, org.id, "hallucination_rate", 0.2, "high")
    await db_session.commit()

    violations = await check_regression_thresholds(db_session, org.id, {"hallucination_rate": 0.5})
    assert len(violations) == 1


async def test_check_regression_thresholds_is_honest_with_a_real_missing_metric(db_session):
    """Validation criterion: robustesse -- métrique manquante."""
    org = await _make_org(db_session, "Threshold Missing Org")
    await db_session.commit()
    await set_regression_threshold(db_session, org.id, "faithfulness", 0.7, "high")
    await db_session.commit()

    violations = await check_regression_thresholds(db_session, org.id, {"answer_relevance": 0.9})
    assert violations == []


async def test_check_regression_thresholds_respects_a_real_disabled_flag(db_session):
    org = await _make_org(db_session, "Threshold Disabled Org")
    await db_session.commit()
    threshold = await set_regression_threshold(db_session, org.id, "faithfulness", 0.7, "high")
    await db_session.commit()
    await update_regression_threshold(db_session, threshold.id, {"enabled": False})
    await db_session.commit()

    violations = await check_regression_thresholds(db_session, org.id, {"faithfulness": 0.1})
    assert violations == []


async def test_update_regression_threshold_is_honestly_none_for_an_unknown_threshold(db_session):
    """Validation criterion: robustesse."""
    assert await update_regression_threshold(db_session, uuid.uuid4(), {"threshold": 0.5}) is None


async def test_delete_regression_threshold_works(db_session):
    org = await _make_org(db_session, "Threshold Delete Org")
    await db_session.commit()
    threshold = await set_regression_threshold(db_session, org.id, "faithfulness", 0.7, "high")
    await db_session.commit()

    deleted = await delete_regression_threshold(db_session, threshold.id)
    await db_session.commit()
    assert deleted is True
    assert await get_regression_threshold(db_session, threshold.id) is None


async def test_delete_regression_threshold_is_honestly_false_for_an_unknown_threshold(db_session):
    """Validation criterion: robustesse."""
    assert await delete_regression_threshold(db_session, uuid.uuid4()) is False

"""api/services/canary_rollout.py -- real orchestration over
api/services/ab_tests.py's own already-tested statistics
(`get_ab_test_results`) and already-tested `pause_ab_test`. Mocked at
that clean boundary -- this test module verifies the real DECISION
logic (rollback vs promote-recommend vs no-op), never re-tests the
underlying A/B statistics themselves (already covered by their own
dedicated test module)."""

import uuid
from unittest.mock import AsyncMock, patch

from api.services.canary_rollout import evaluate_canary


async def _make_running_test(db_session, traffic_split=50):
    from api.models.organization import Organization
    from api.services.ab_tests import create_ab_test, start_ab_test

    org = Organization(name="Canary Org", slug=f"canary-org-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    test = await create_ab_test(
        db_session, org.id, "Canary Test", variant_a={"system_prompt": "baseline"},
        variant_b={"system_prompt": "candidate"}, traffic_split=traffic_split,
    )
    await db_session.commit()
    test = await start_ab_test(db_session, test.id)
    await db_session.commit()
    return test


def _metric_result(lift, significant, min_sample_size_reached=True):
    return {
        "variant_a": {"count": 100, "mean": 0.8, "std_dev": 0.1}, "variant_b": {"count": 100, "mean": 0.8, "std_dev": 0.1},
        "lift": lift, "p_value": 0.01 if significant else 0.5, "significant": significant,
        "confidence_interval_lower": None, "confidence_interval_upper": None, "effect_size_cohens_d": None,
        "statistical_power": None, "min_sample_size_reached": min_sample_size_reached,
    }


async def test_evaluate_canary_auto_rolls_back_a_real_significant_regression(db_session):
    test = await _make_running_test(db_session)

    with patch("api.services.ab_tests.get_ab_test_results", AsyncMock(return_value={
        "test_id": test.id, "status": "running", "metrics": {"semantic_similarity": _metric_result(-0.10, True)},
    })):
        result = await evaluate_canary(db_session, test.id, "semantic_similarity")

    assert result["action"] == "rolled_back"
    await db_session.refresh(test)
    assert test.status == "paused"


async def test_evaluate_canary_recommends_promotion_without_auto_applying_it(db_session):
    test = await _make_running_test(db_session, traffic_split=20)

    with patch("api.services.ab_tests.get_ab_test_results", AsyncMock(return_value={
        "test_id": test.id, "status": "running", "metrics": {"semantic_similarity": _metric_result(0.15, True)},
    })):
        result = await evaluate_canary(db_session, test.id, "semantic_similarity")

    assert result["action"] == "promotion_recommended"
    assert result["recommended_traffic_split"] == 30
    await db_session.refresh(test)
    assert test.traffic_split == 20  # never auto-applied
    assert test.status == "running"


async def test_evaluate_canary_does_nothing_without_enough_real_samples(db_session):
    test = await _make_running_test(db_session)

    with patch("api.services.ab_tests.get_ab_test_results", AsyncMock(return_value={
        "test_id": test.id, "status": "running",
        "metrics": {"semantic_similarity": _metric_result(-0.20, True, min_sample_size_reached=False)},
    })):
        result = await evaluate_canary(db_session, test.id, "semantic_similarity")

    assert result["action"] == "none"
    await db_session.refresh(test)
    assert test.status == "running"


async def test_evaluate_canary_does_nothing_for_a_non_significant_effect(db_session):
    test = await _make_running_test(db_session)

    with patch("api.services.ab_tests.get_ab_test_results", AsyncMock(return_value={
        "test_id": test.id, "status": "running", "metrics": {"semantic_similarity": _metric_result(-0.10, False)},
    })):
        result = await evaluate_canary(db_session, test.id, "semantic_similarity")

    assert result["action"] == "none"


async def test_evaluate_canary_does_nothing_for_a_test_that_is_not_running(db_session):
    from api.services.ab_tests import pause_ab_test

    test = await _make_running_test(db_session)
    await pause_ab_test(db_session, test.id)
    await db_session.commit()

    result = await evaluate_canary(db_session, test.id, "semantic_similarity")
    assert result["action"] == "none"

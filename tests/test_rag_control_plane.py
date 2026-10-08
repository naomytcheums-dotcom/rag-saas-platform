"""api/services/rag_control_plane.py -- real orchestration over item 19
(rag_genome) and item 20 (canary_rollout)'s own already-tested
functions. `evaluate_canary` is mocked at its own clean, already-tested
boundary -- this test module verifies the real BATCHING logic across
an organization's real, concurrent ABTest rows, never re-tests canary
statistics themselves."""

import uuid
from unittest.mock import AsyncMock, patch

# Real, explicit, module-level import -- `RagExperiment` (item 19) is
# only ever imported LOCALLY inside `run_health_check`'s own function
# body (a real, deliberate choice so `rag_control_plane.py` never
# forces every caller to pay for importing `rag_genome`/`canary_rollout`
# just to import this module) -- this test file needs it registered
# with `Base.metadata` BEFORE the `db_session` fixture below creates
# its real, fresh SQLite schema, same real "model only referenced via
# a local import needs an explicit test-level import first" pattern as
# tests/test_rag_evolution_engine.py's own `_make_dataset` helper.
from api.models.rag_experiment import RagExperiment  # noqa: F401
from api.services.rag_control_plane import run_health_check


async def _make_org(db_session):
    from api.models.organization import Organization

    org = Organization(name="Control Plane Org", slug=f"control-plane-org-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


async def _make_running_ab_test(db_session, org_id, target_metric=None):
    from api.services.ab_tests import create_ab_test, start_ab_test

    test = await create_ab_test(
        db_session, org_id, "Health Check Test", variant_a={"system_prompt": "a"}, variant_b={"system_prompt": "b"},
        target_metric=target_metric,
    )
    await db_session.commit()
    test = await start_ab_test(db_session, test.id)
    await db_session.commit()
    return test


async def test_run_health_check_evaluates_every_real_running_canary(db_session):
    org = await _make_org(db_session)
    test_a = await _make_running_ab_test(db_session, org.id)
    test_b = await _make_running_ab_test(db_session, org.id)

    mock_evaluate = AsyncMock(return_value={"action": "none", "reason": "no significant effect yet"})
    with patch("api.services.canary_rollout.evaluate_canary", mock_evaluate):
        report = await run_health_check(db_session, org.id)

    assert report["running_canaries_evaluated"] == 2
    assert mock_evaluate.await_count == 2
    evaluated_test_ids = {call.args[1] for call in mock_evaluate.await_args_list}
    assert evaluated_test_ids == {test_a.id, test_b.id}


async def test_run_health_check_uses_each_tests_own_real_target_metric(db_session):
    org = await _make_org(db_session)
    test = await _make_running_ab_test(db_session, org.id, target_metric="error_rate")

    mock_evaluate = AsyncMock(return_value={"action": "none", "reason": "no significant effect yet"})
    with patch("api.services.canary_rollout.evaluate_canary", mock_evaluate):
        await run_health_check(db_session, org.id, default_target_metric="conversion_rate")

    mock_evaluate.assert_awaited_once_with(db_session, test.id, "error_rate")


async def test_run_health_check_falls_back_to_the_default_target_metric(db_session):
    org = await _make_org(db_session)
    test = await _make_running_ab_test(db_session, org.id, target_metric=None)

    mock_evaluate = AsyncMock(return_value={"action": "none", "reason": "no significant effect yet"})
    with patch("api.services.canary_rollout.evaluate_canary", mock_evaluate):
        await run_health_check(db_session, org.id, default_target_metric="conversion_rate")

    mock_evaluate.assert_awaited_once_with(db_session, test.id, "conversion_rate")


async def test_run_health_check_ignores_non_running_tests(db_session):
    org = await _make_org(db_session)
    from api.services.ab_tests import create_ab_test

    await create_ab_test(db_session, org.id, "Draft Test", variant_a={"a": 1}, variant_b={"b": 1})
    await db_session.commit()

    mock_evaluate = AsyncMock()
    with patch("api.services.canary_rollout.evaluate_canary", mock_evaluate):
        report = await run_health_check(db_session, org.id)

    assert report["running_canaries_evaluated"] == 0
    mock_evaluate.assert_not_awaited()


async def test_run_health_check_includes_real_recent_experiments(db_session):
    from api.services.rag_genome import record_experiment

    org = await _make_org(db_session)
    await record_experiment(db_session, org.id, {"system_prompt": "x"}, source="manual", decision="baseline_kept")
    await db_session.commit()

    report = await run_health_check(db_session, org.id)

    assert len(report["recent_experiments"]) == 1
    assert report["recent_experiments"][0]["decision"] == "baseline_kept"


async def test_run_health_check_with_no_real_activity_at_all(db_session):
    org = await _make_org(db_session)
    report = await run_health_check(db_session, org.id)

    assert report["running_canaries_evaluated"] == 0
    assert report["canary_results"] == []
    assert report["recent_experiments"] == []

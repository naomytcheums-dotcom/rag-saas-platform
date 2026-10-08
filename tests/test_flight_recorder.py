"""api/services/flight_recorder.py -- real, additive persistence, no
mocking needed."""

import time
import uuid

from api.services.flight_recorder import StageTimer, get_flight_recording, list_flight_recordings, record_flight


async def _make_org(db_session):
    from api.models.organization import Organization

    org = Organization(name="Flight Org", slug=f"flight-org-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    return org


def test_stage_timer_records_a_real_duration_and_data():
    with StageTimer("bm25_search") as t:
        t.data["candidate_count"] = 42
        time.sleep(0.01)

    assert t.record["stage"] == "bm25_search"
    assert t.record["data"] == {"candidate_count": 42}
    assert t.record["duration_ms"] >= 10


async def test_record_flight_persists_a_real_stage_trace(db_session):
    org = await _make_org(db_session)
    stages = [
        {"stage": "query_rewriting", "data": {"rewritten": "refund policy"}, "duration_ms": 50},
        {"stage": "bm25_search", "data": {"candidate_count": 20}, "duration_ms": 15},
        {"stage": "rerank", "data": {"final_count": 5}, "duration_ms": 80},
    ]

    recording = await record_flight(db_session, org.id, "what is the refund policy?", stages, total_duration_ms=145)
    await db_session.commit()

    assert recording.organization_id == org.id
    assert recording.stages_json == stages
    assert recording.total_duration_ms == 145


async def test_get_flight_recording_returns_none_for_an_unknown_id(db_session):
    result = await get_flight_recording(db_session, uuid.uuid4())
    assert result is None


async def test_get_flight_recording_replays_the_real_stage_order(db_session):
    org = await _make_org(db_session)
    stages = [{"stage": "a", "data": {}, "duration_ms": 1}, {"stage": "b", "data": {}, "duration_ms": 2}]
    recording = await record_flight(db_session, org.id, "q", stages)
    await db_session.commit()

    fetched = await get_flight_recording(db_session, recording.id)
    assert [s["stage"] for s in fetched.stages_json] == ["a", "b"]


async def test_list_flight_recordings_never_leaks_across_organizations(db_session):
    org_a = await _make_org(db_session)
    org_b = await _make_org(db_session)
    await record_flight(db_session, org_a.id, "q1", [])
    await db_session.commit()

    results_for_b = await list_flight_recordings(db_session, org_b.id)
    assert results_for_b == []

"""Partie 5.1.14 -- agent traces. Fast SQLite suite."""

import json
import uuid

import pytest
from sqlalchemy import select

from api.config import settings
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.security.agent_runs import create_run
from api.services.agent_traces import end_trace, export_agent_traces, get_agent_trace_tree, get_agent_traces, purge_expired_traces, start_trace


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _create_org(client, access_token: str, name: str) -> dict:
    return (await client.post("/organizations", json={"name": name}, headers=_auth_header(access_token))).json()


async def _make_run(db_session, organization_id=None):
    run = await create_run(db_session, agent_id="agent-1", input="do something", organization_id=organization_id)
    await db_session.commit()
    return run


# --------------------------------------- start_trace / end_trace --


async def test_start_trace_creates_a_real_step(db_session):
    """Validation criterion: l'enregistrement des traces fonctionne."""
    run = await _make_run(db_session)
    trace = await start_trace(db_session, run.id, "llm_call", "call the model")
    await db_session.commit()

    assert trace.step_number == 0
    assert trace.status == "started"


async def test_end_trace_computes_a_real_duration(db_session):
    run = await _make_run(db_session)
    trace = await start_trace(db_session, run.id, "llm_call", "call the model")
    await db_session.commit()

    ended = await end_trace(db_session, trace.id, output={"text": "ok"}, status="completed")
    await db_session.commit()

    assert ended.status == "completed"
    assert ended.duration_ms is not None
    assert ended.duration_ms >= 0


async def test_end_trace_returns_none_for_unknown_id(db_session):
    assert await end_trace(db_session, uuid.uuid4()) is None


async def test_start_trace_enforces_the_real_max_steps_limit(db_session, monkeypatch):
    """Validation criterion: les limites sont respectées."""
    monkeypatch.setattr(settings, "AGENT_TRACES_MAX_STEPS", 1)
    run = await _make_run(db_session)
    await start_trace(db_session, run.id, "llm_call", "first")
    await db_session.commit()

    with pytest.raises(ValueError):
        await start_trace(db_session, run.id, "llm_call", "second")


async def test_start_trace_disabled_still_returns_a_real_object(db_session, monkeypatch):
    monkeypatch.setattr(settings, "AGENT_TRACES_ENABLED", False)
    run = await _make_run(db_session)
    trace = await start_trace(db_session, run.id, "llm_call", "call")
    assert trace.description == "call"


# --------------------------------------- get_agent_traces / tree --


async def test_get_agent_traces_returns_real_ordered_steps(db_session):
    """Validation criterion: la récupération des traces fonctionne."""
    run = await _make_run(db_session)
    await start_trace(db_session, run.id, "planning", "plan")
    await start_trace(db_session, run.id, "llm_call", "call")
    await db_session.commit()

    traces = await get_agent_traces(db_session, run.id)
    assert [t.step_type for t in traces] == ["planning", "llm_call"]


async def test_get_agent_trace_tree_groups_by_step_type(db_session):
    run = await _make_run(db_session)
    await start_trace(db_session, run.id, "llm_call", "first call")
    await start_trace(db_session, run.id, "llm_call", "second call")
    await start_trace(db_session, run.id, "planning", "plan")
    await db_session.commit()

    tree = await get_agent_trace_tree(db_session, run.id)
    assert len(tree["llm_call"]) == 2
    assert len(tree["planning"]) == 1


# --------------------------------------- export --


async def test_export_agent_traces_json(db_session):
    """Validation criterion: l'export fonctionne."""
    run = await _make_run(db_session)
    await start_trace(db_session, run.id, "llm_call", "call")
    await db_session.commit()

    exported = await export_agent_traces(db_session, run.id, "json")
    parsed = json.loads(exported)
    assert parsed[0]["description"] == "call"


async def test_export_agent_traces_html(db_session):
    run = await _make_run(db_session)
    await start_trace(db_session, run.id, "llm_call", "call")
    await db_session.commit()

    exported = await export_agent_traces(db_session, run.id, "html")
    assert "<table>" in exported
    assert "call" in exported


async def test_export_agent_traces_rejects_an_unsupported_format(db_session):
    run = await _make_run(db_session)
    with pytest.raises(ValueError):
        await export_agent_traces(db_session, run.id, "xml")


# --------------------------------------- retention --


async def test_purge_expired_traces_removes_only_real_old_traces(db_session, monkeypatch):
    """Validation criterion: robustesse -- stockage nettoyé."""
    import datetime as dt
    monkeypatch.setattr(settings, "AGENT_TRACES_RETENTION_DAYS", 30)
    run = await _make_run(db_session)
    old_trace = await start_trace(db_session, run.id, "llm_call", "old")
    old_trace.created_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=60)
    fresh_trace = await start_trace(db_session, run.id, "llm_call", "fresh")
    await db_session.commit()

    removed = await purge_expired_traces(db_session)
    await db_session.commit()

    assert removed == 1
    remaining = await get_agent_traces(db_session, run.id)
    assert [t.id for t in remaining] == [fresh_trace.id]


# --------------------------------------- endpoints --


async def test_org_member_can_list_and_export_traces(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    org_id = uuid.UUID(org["id"])
    run = await _make_run(db_session, organization_id=org_id)
    await start_trace(db_session, run.id, "llm_call", "call")
    await db_session.commit()

    listing = await client.get(f"/organizations/{org['id']}/agents/runs/{run.id}/traces", headers=_auth_header(owner_token))
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    tree = await client.get(f"/organizations/{org['id']}/agents/runs/{run.id}/traces/tree", headers=_auth_header(owner_token))
    assert tree.status_code == 200

    export = await client.get(f"/organizations/{org['id']}/agents/runs/{run.id}/traces/export", headers=_auth_header(owner_token))
    assert export.status_code == 200


async def test_cannot_read_traces_for_a_run_in_another_organization(client, db_session, register_payload):
    """Validation criterion: sécurité."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    other_org_id = uuid.uuid4()
    run = await _make_run(db_session, organization_id=other_org_id)

    response = await client.get(f"/organizations/{org['id']}/agents/runs/{run.id}/traces", headers=_auth_header(owner_token))
    assert response.status_code == 404

"""SEC-004: Twilio call management must be tenant-scoped.

Before the fix `GET /twilio/calls`, `POST /twilio/outbound` and `POST /twilio/{sid}/end` only required *a* logged-in user: any
registered account could read every tenant's call transcripts, place calls on the platform's Twilio account with another tenant's
agent, and end other tenants' calls. Twilio itself is always mocked here; no call leaves the test process."""

import datetime as dt
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from api.config import settings
from api.models.agent import Agent
from api.models.audit_log import AuditLog
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User, UserRole
from api.models.voice import CallRecord
from api.security import rate_limit as rate_limit_module
from api.security.jwt import create_access_token
from api.services.telephony import (
    handle_incoming_call, handle_speech_input, list_organization_calls, make_outbound_call, place_organization_call,
)
from test_document_idor import make_tenants


@pytest.fixture(autouse=True)
def _twilio_configured(monkeypatch):
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "fake-token")
    monkeypatch.setattr(settings, "TWILIO_WEBHOOK_URL", "https://myapp.example.com")
    monkeypatch.setattr(settings, "TWILIO_PHONE_NUMBER", "+15559876543")


@pytest.fixture
def twilio_client():
    client = MagicMock()
    sids = iter(f"CA-NEW-{index}" for index in range(100))
    client.calls.create.side_effect = lambda **kwargs: MagicMock(sid=next(sids))
    with patch("api.services.telephony.Client", return_value=client):
        yield client


async def _world(client, db_session, monkeypatch):
    (headers_a, org_a, user_a), (headers_b, org_b, user_b) = await make_tenants(client, db_session, monkeypatch, "twilio")
    agent_a = Agent(organization_id=org_a, name="A agent", system_prompt="You answer for A.")
    agent_b = Agent(organization_id=org_b, name="B agent", system_prompt="You answer for B.")
    db_session.add_all([agent_a, agent_b])
    await db_session.flush()
    call_a = CallRecord(
        call_sid="CA-A", organization_id=org_a, agent_id=agent_a.id, from_number="+15550001", to_number="+15550002",
        status="completed", transcription="A-PRIVATE-TRANSCRIPT",
    )
    call_b = CallRecord(
        call_sid="CA-B", organization_id=org_b, agent_id=agent_b.id, from_number="+15550003", to_number="+15550004",
        status="completed", transcription="B-PRIVATE-TRANSCRIPT",
    )
    legacy = CallRecord(
        call_sid="CA-OLD", from_number="+15550005", to_number="+15550006", status="completed", transcription="LEGACY-TRANSCRIPT",
    )
    db_session.add_all([call_a, call_b, legacy])
    await db_session.commit()
    return {
        "headers_a": headers_a, "org_a": org_a, "user_a": user_a, "agent_a": agent_a.id,
        "headers_b": headers_b, "org_b": org_b, "user_b": user_b, "agent_b": agent_b.id,
    }


async def _member_headers(db_session, org_id, role, email):
    user = User(
        email=email, hashed_password="unused", is_email_verified=True,
        terms_version=settings.TERMS_VERSION, consent_given_at=dt.datetime.now(dt.timezone.utc),
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(OrganizationMember(organization_id=org_id, user_id=user.id, role=role))
    await db_session.commit()
    token, _ = create_access_token(user.id)
    return {"Authorization": f"Bearer {token}"}


# ------------------------------------------------------------ legacy platform-wide routes


async def test_legacy_routes_reject_ordinary_users_and_anonymous(client, db_session, monkeypatch, twilio_client):
    world = await _world(client, db_session, monkeypatch)
    for headers in (world["headers_a"], world["headers_b"]):
        assert (await client.get("/twilio/calls", headers=headers)).status_code == 403
        outbound = await client.post(f"/twilio/outbound?to=%2B15551234567&agent_id={world['agent_b']}", headers=headers)
        assert outbound.status_code == 403
        assert (await client.post("/twilio/CA-B/end", headers=headers)).status_code == 403
    for method, url in (("GET", "/twilio/calls"), ("POST", "/twilio/outbound?to=%2B15551234567&agent_id=x"), ("POST", "/twilio/CA-B/end")):
        assert (await client.request(method, url)).status_code in (401, 403)
    twilio_client.calls.create.assert_not_called()
    twilio_client.calls.assert_not_called()


async def test_legacy_routes_still_work_for_a_platform_superadmin(client, db_session, monkeypatch, twilio_client):
    world = await _world(client, db_session, monkeypatch)
    admin = await db_session.get(User, world["user_a"])
    admin.role = UserRole.superadmin
    await db_session.commit()

    listing = await client.get("/twilio/calls", headers=world["headers_a"])
    assert listing.status_code == 200
    assert {row["call_sid"] for row in listing.json()} == {"CA-A", "CA-B", "CA-OLD"}
    outbound = await client.post(f"/twilio/outbound?to=%2B15551234567&agent_id={world['agent_a']}", headers=world["headers_a"])
    assert outbound.status_code == 200 and outbound.json() == {"call_sid": "CA-NEW-0"}
    assert (await client.post("/twilio/CA-A/end", headers=world["headers_a"])).status_code == 204


# ------------------------------------------------------------ organization-scoped history


async def test_each_tenant_only_lists_its_own_calls(client, db_session, monkeypatch):
    world = await _world(client, db_session, monkeypatch)

    own_a = await client.get(f"/organizations/{world['org_a']}/twilio/calls", headers=world["headers_a"])
    own_b = await client.get(f"/organizations/{world['org_b']}/twilio/calls", headers=world["headers_b"])

    assert own_a.status_code == 200 and [row["call_sid"] for row in own_a.json()] == ["CA-A"]
    assert own_b.status_code == 200 and [row["call_sid"] for row in own_b.json()] == ["CA-B"]
    leaked = await client.get(f"/organizations/{world['org_a']}/twilio/calls", headers=world["headers_b"])
    assert leaked.status_code in (403, 404)
    assert "A-PRIVATE-TRANSCRIPT" not in leaked.text and "LEGACY-TRANSCRIPT" not in leaked.text
    assert "LEGACY-TRANSCRIPT" not in own_a.text + own_b.text


async def test_history_requires_authentication_and_supports_paging(client, db_session, monkeypatch):
    world = await _world(client, db_session, monkeypatch)
    assert (await client.get(f"/organizations/{world['org_a']}/twilio/calls")).status_code in (401, 403)
    for index in range(3):
        db_session.add(CallRecord(call_sid=f"CA-A{index}", organization_id=world["org_a"], from_number="x", to_number="y", status="completed"))
    await db_session.commit()
    page = await client.get(f"/organizations/{world['org_a']}/twilio/calls?limit=2&offset=0", headers=world["headers_a"])
    assert page.status_code == 200 and len(page.json()) == 2
    assert (await client.get(f"/organizations/{world['org_a']}/twilio/calls?limit=0", headers=world["headers_a"])).status_code == 422


# ------------------------------------------------------------ outbound calls


async def test_outbound_call_is_recorded_under_the_callers_organization(client, db_session, monkeypatch, twilio_client):
    world = await _world(client, db_session, monkeypatch)

    response = await client.post(
        f"/organizations/{world['org_a']}/twilio/outbound", json={"to": "+15551234567", "agent_id": str(world["agent_a"])},
        headers=world["headers_a"],
    )

    assert response.status_code == 201, response.text
    assert response.json()["call_sid"] == "CA-NEW-0"
    kwargs = twilio_client.calls.create.call_args.kwargs
    assert kwargs["from_"] == "+15559876543"  # the platform number; a tenant never chooses the caller id
    assert kwargs["url"] == f"https://myapp.example.com/twilio/incoming?agent_id={world['agent_a']}"
    row = await db_session.scalar(select(CallRecord).where(CallRecord.call_sid == "CA-NEW-0"))
    assert row.organization_id == world["org_a"] and row.agent_id == world["agent_a"]
    audit = (await db_session.scalars(select(AuditLog).where(AuditLog.action == "telephony_call_placed"))).all()
    assert len(audit) == 1 and audit[0].organization_id == world["org_a"]


async def test_outbound_call_with_another_tenants_agent_is_refused(client, db_session, monkeypatch, twilio_client):
    world = await _world(client, db_session, monkeypatch)

    foreign = await client.post(
        f"/organizations/{world['org_a']}/twilio/outbound", json={"to": "+15551234567", "agent_id": str(world["agent_b"])},
        headers=world["headers_a"],
    )
    unknown = await client.post(
        f"/organizations/{world['org_a']}/twilio/outbound", json={"to": "+15551234567", "agent_id": str(uuid.uuid4())},
        headers=world["headers_a"],
    )
    other_org = await client.post(
        f"/organizations/{world['org_a']}/twilio/outbound", json={"to": "+15551234567", "agent_id": str(world["agent_a"])},
        headers=world["headers_b"],
    )

    assert foreign.status_code == 404 and unknown.status_code == 404
    assert foreign.json() == unknown.json()  # "someone else's" is indistinguishable from "absent"
    assert other_org.status_code in (403, 404)
    twilio_client.calls.create.assert_not_called()
    assert await db_session.scalar(select(CallRecord).where(CallRecord.call_sid == "CA-NEW-0")) is None


@pytest.mark.parametrize("target", ["sip:agent@evil.example", "client:alice", "15551234567", "+0123456789", "+1555123456789012345", "+1555; drop", ""])
async def test_outbound_destination_must_be_an_e164_number(client, db_session, monkeypatch, twilio_client, target):
    world = await _world(client, db_session, monkeypatch)
    response = await client.post(
        f"/organizations/{world['org_a']}/twilio/outbound", json={"to": target, "agent_id": str(world["agent_a"])}, headers=world["headers_a"],
    )
    assert response.status_code == 422
    twilio_client.calls.create.assert_not_called()


async def test_outbound_and_end_require_integration_write_permission(client, db_session, monkeypatch, twilio_client):
    world = await _world(client, db_session, monkeypatch)
    for role in (OrganizationRole.member, OrganizationRole.viewer):
        headers = await _member_headers(db_session, world["org_a"], role, f"twilio-{role.value}@example.com")
        placed = await client.post(
            f"/organizations/{world['org_a']}/twilio/outbound", json={"to": "+15551234567", "agent_id": str(world["agent_a"])}, headers=headers,
        )
        ended = await client.post(f"/organizations/{world['org_a']}/twilio/calls/CA-A/end", headers=headers)
        assert placed.status_code == 403 and ended.status_code == 403
    manager = await _member_headers(db_session, world["org_a"], OrganizationRole.manager, "twilio-manager@example.com")
    allowed = await client.post(
        f"/organizations/{world['org_a']}/twilio/outbound", json={"to": "+15551234567", "agent_id": str(world["agent_a"])}, headers=manager,
    )
    assert allowed.status_code == 201, allowed.text
    assert twilio_client.calls.create.call_count == 1


async def test_outbound_calls_are_rate_limited_per_organization(client, db_session, monkeypatch, twilio_client):
    world = await _world(client, db_session, monkeypatch)
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "TWILIO_OUTBOUND_RATE_LIMIT_MAX_ATTEMPTS", 1)
    monkeypatch.setattr(rate_limit_module, "_get_redis", MagicMock(side_effect=ConnectionError("no redis in tests")))
    rate_limit_module._local_windows.clear()
    try:
        body = {"to": "+15551234567", "agent_id": str(world["agent_a"])}
        first = await client.post(f"/organizations/{world['org_a']}/twilio/outbound", json=body, headers=world["headers_a"])
        second = await client.post(f"/organizations/{world['org_a']}/twilio/outbound", json=body, headers=world["headers_a"])
        other_tenant = await client.post(
            f"/organizations/{world['org_b']}/twilio/outbound", json={**body, "agent_id": str(world["agent_b"])}, headers=world["headers_b"],
        )
    finally:
        rate_limit_module._local_windows.clear()
    assert first.status_code == 201 and second.status_code == 429
    assert other_tenant.status_code == 201  # the budget is per organization
    assert twilio_client.calls.create.call_count == 2


async def test_agent_id_is_url_encoded_in_the_callback_url(twilio_client):
    await make_outbound_call("+15551234567", None, "x&organization_id=evil#frag")
    assert twilio_client.calls.create.call_args.kwargs["url"].endswith("/twilio/incoming?agent_id=x%26organization_id%3Devil%23frag")


# ------------------------------------------------------------ ending calls


async def test_a_tenant_can_end_only_its_own_calls(client, db_session, monkeypatch, twilio_client):
    world = await _world(client, db_session, monkeypatch)

    foreign = await client.post(f"/organizations/{world['org_a']}/twilio/calls/CA-B/end", headers=world["headers_a"])
    legacy_row = await client.post(f"/organizations/{world['org_a']}/twilio/calls/CA-OLD/end", headers=world["headers_a"])
    unknown = await client.post(f"/organizations/{world['org_a']}/twilio/calls/CA-NOPE/end", headers=world["headers_a"])
    other_org = await client.post(f"/organizations/{world['org_a']}/twilio/calls/CA-A/end", headers=world["headers_b"])
    assert (foreign.status_code, legacy_row.status_code, unknown.status_code) == (404, 404, 404)
    assert other_org.status_code in (403, 404)
    twilio_client.calls.assert_not_called()

    own = await client.post(f"/organizations/{world['org_a']}/twilio/calls/CA-A/end", headers=world["headers_a"])
    assert own.status_code == 204
    twilio_client.calls.assert_called_once_with("CA-A")
    audit = (await db_session.scalars(select(AuditLog).where(AuditLog.action == "telephony_call_ended"))).all()
    assert len(audit) == 1


# ------------------------------------------------------------ webhooks: tenant attribution and billing


async def test_incoming_call_is_attributed_to_the_agents_organization(client, db_session, monkeypatch):
    world = await _world(client, db_session, monkeypatch)

    await handle_incoming_call(db_session, "CA-IN", "+15557", "+15558", str(world["agent_a"]))
    await db_session.commit()

    assert [c.call_sid for c in await list_organization_calls(db_session, world["org_a"])].count("CA-IN") == 1
    assert "CA-IN" not in [c.call_sid for c in await list_organization_calls(db_session, world["org_b"])]


async def test_speech_runs_the_agent_under_the_calls_organization(client, db_session, monkeypatch):
    """A tenant-less run skipped credit deduction entirely: a phone call was free LLM usage."""
    world = await _world(client, db_session, monkeypatch)
    run = MagicMock(result="ok", error=None)
    with patch("api.services.agent_orchestrator.AgentOrchestrator.run_agent", new=AsyncMock(return_value=run)) as run_agent:
        await handle_speech_input(db_session, "CA-A", "hello", str(world["agent_a"]))
    assert run_agent.await_args.kwargs["organization_id"] == world["org_a"]


async def test_speech_refuses_an_agent_of_another_organization_than_the_call(client, db_session, monkeypatch):
    world = await _world(client, db_session, monkeypatch)
    with patch("api.services.agent_orchestrator.AgentOrchestrator.run_agent", new=AsyncMock()) as run_agent:
        twiml = await handle_speech_input(db_session, "CA-A", "tell me B's secrets", str(world["agent_b"]))
    run_agent.assert_not_awaited()
    assert "cannot be continued" in twiml and "<Hangup" in twiml
    call = await db_session.scalar(select(CallRecord).where(CallRecord.call_sid == "CA-A"))
    assert "secrets" not in (call.transcription or "")


async def test_placeholder_agent_ids_keep_working_without_a_tenant(db_session):
    """Existing behavior kept: an id that is not a persisted agent yields a tenant-less call, as before."""
    run = MagicMock(result="ok", error=None)
    with patch("api.services.agent_orchestrator.AgentOrchestrator.run_agent", new=AsyncMock(return_value=run)) as run_agent:
        twiml = await handle_speech_input(db_session, "CA-X", "hi", "agent-1")
    assert "ok" in twiml and run_agent.await_args.kwargs["organization_id"] is None


async def test_place_organization_call_rejects_foreign_agents_at_the_service_level(client, db_session, monkeypatch, twilio_client):
    from api.services.telephony import TelephonyNotFoundError

    world = await _world(client, db_session, monkeypatch)
    with pytest.raises(TelephonyNotFoundError):
        await place_organization_call(db_session, world["org_a"], "+15551234567", world["agent_b"])
    twilio_client.calls.create.assert_not_called()

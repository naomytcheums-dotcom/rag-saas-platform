"""Spec 10.4.12 (custom SLA): the requirement had no testable criterion. Acceptance criterion now written and tested here:

  An organization can set its own answer-by delay, in hours, for each escalation priority (organization setting `escalation_sla_hours`); a ticket created
  for that organization carries `sla_due_at = creation time + that delay`; a priority it does not set, and every other organization, keep the platform default
  (`ESCALATION_SLA_HOURS`); invalid delays are refused with 422.

The commercial side (uptime commitments, credits, support hours) stays a contract matter outside the code (docs/commercial)."""

import datetime as dt
import uuid

import pytest
from sqlalchemy import select

from api.config import settings
from api.models.user import User
from api.security.agent_runs import create_run
from api.tools.human_escalation import escalate_to_human


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _owner_with_org(client, db_session, email, password):
    token = (await client.post("/auth/register", json={"email": email, "password": password, "accept_terms": True})).json()["access_token"]
    org = (await client.post("/organizations", json={"name": f"Sla {uuid.uuid4().hex[:6]}"}, headers=_auth(token))).json()
    user = await db_session.scalar(select(User).where(User.email == email))
    return token, org, user


def _hours_until(escalation) -> float:
    due = escalation.sla_due_at if escalation.sla_due_at.tzinfo else escalation.sla_due_at.replace(tzinfo=dt.timezone.utc)
    return (due - dt.datetime.now(dt.timezone.utc)).total_seconds() / 3600


async def _ticket(db_session, org_id, priority):
    run = await create_run(db_session, agent_id="agent-1", input="help", organization_id=org_id)
    await db_session.commit()
    escalation = await escalate_to_human(db_session, run.id, "customer is blocked", priority=priority, organization_id=org_id)
    await db_session.commit()
    return escalation


async def test_an_owner_can_set_and_read_back_custom_sla_delays(client, db_session, register_payload):
    token, org, _ = await _owner_with_org(client, db_session, register_payload["email"], register_payload["password"])
    response = await client.patch(f"/organizations/{org['id']}/settings", json={"escalation_sla_hours": {"critical": 2, "low": 120}}, headers=_auth(token))
    assert response.status_code == 200, response.text
    assert response.json()["escalation_sla_hours"] == {"critical": 2, "low": 120}
    assert (await client.get(f"/organizations/{org['id']}/settings", headers=_auth(token))).json()["escalation_sla_hours"] == {"critical": 2, "low": 120}


@pytest.mark.parametrize("bad", [{"urgent": 2}, {"critical": 0}, {"critical": 721}, {"critical": True}, {"critical": -3}])
async def test_invalid_sla_delays_are_refused(client, db_session, register_payload, bad):
    token, org, _ = await _owner_with_org(client, db_session, register_payload["email"], register_payload["password"])
    response = await client.patch(f"/organizations/{org['id']}/settings", json={"escalation_sla_hours": bad}, headers=_auth(token))
    assert response.status_code == 422, response.text


async def test_a_ticket_uses_the_organization_delay_and_other_priorities_keep_the_default(client, db_session, register_payload):
    token, org, _ = await _owner_with_org(client, db_session, register_payload["email"], register_payload["password"])
    assert (await client.patch(f"/organizations/{org['id']}/settings", json={"escalation_sla_hours": {"critical": 2}}, headers=_auth(token))).status_code == 200
    org_id = uuid.UUID(org["id"])

    critical = await _ticket(db_session, org_id, "critical")
    high = await _ticket(db_session, org_id, "high")

    assert _hours_until(critical) == pytest.approx(2, abs=0.05)
    assert _hours_until(high) == pytest.approx(settings.ESCALATION_SLA_HOURS["high"], abs=0.05)


async def test_another_organization_keeps_the_platform_default(client, db_session, register_payload):
    token, org, _ = await _owner_with_org(client, db_session, register_payload["email"], register_payload["password"])
    assert (await client.patch(f"/organizations/{org['id']}/settings", json={"escalation_sla_hours": {"critical": 2}}, headers=_auth(token))).status_code == 200

    other_token, other, _ = await _owner_with_org(client, db_session, "other-sla-owner@example.com", register_payload["password"])
    ticket = await _ticket(db_session, uuid.UUID(other["id"]), "critical")

    assert _hours_until(ticket) == pytest.approx(settings.ESCALATION_SLA_HOURS["critical"], abs=0.05)
    assert other_token  # the second owner exists and has no override


async def test_a_ticket_without_an_organization_uses_the_platform_default(db_session):
    run = await create_run(db_session, agent_id="agent-1", input="help")
    await db_session.commit()
    ticket = await escalate_to_human(db_session, run.id, "no org", priority="medium")
    assert _hours_until(ticket) == pytest.approx(settings.ESCALATION_SLA_HOURS["medium"], abs=0.05)

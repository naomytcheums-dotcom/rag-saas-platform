"""Spec 15.1 -- escalation tickets API (ticket id, priority, assignment, SLA, status, internal notes, resolution). Fast SQLite suite."""

import datetime as dt
import uuid

from sqlalchemy import select

from api.config import settings
from api.models.escalation import Escalation
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.security.agent_runs import create_run
from api.tools.human_escalation import escalate_to_human


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _register(client, db_session, email: str):
    token = (await client.post("/auth/register", json={"email": email, "password": "correct-horse-battery-staple", "accept_terms": True})).json()["access_token"]
    return token, await db_session.scalar(select(User).where(User.email == email))


async def _org_with_ticket(client, db_session, owner_email="owner-esc@example.com", priority="high"):
    token, owner = await _register(client, db_session, owner_email)
    org = (await client.post("/organizations", json={"name": "Esc Org"}, headers=_h(token))).json()
    run = await create_run(db_session, agent_id="agent-1", input="stuck", organization_id=uuid.UUID(org["id"]))
    await db_session.commit()
    ticket = await escalate_to_human(db_session, run.id, "Cannot find the contract", priority=priority, organization_id=uuid.UUID(org["id"]))
    await db_session.commit()
    return token, owner, org, ticket


async def test_a_ticket_gets_an_id_a_priority_and_an_sla_deadline_from_its_priority(client, db_session):
    _token, _owner, _org, ticket = await _org_with_ticket(client, db_session, priority="critical")
    assert ticket.id and ticket.priority == "critical"
    hours = (ticket.sla_due_at - dt.datetime.now(dt.timezone.utc)).total_seconds() / 3600 if ticket.sla_due_at.tzinfo else (ticket.sla_due_at - dt.datetime.utcnow()).total_seconds() / 3600
    assert 0.9 < hours <= settings.ESCALATION_SLA_HOURS["critical"] + 0.01


async def test_list_filter_and_get(client, db_session):
    token, _owner, org, ticket = await _org_with_ticket(client, db_session)
    listing = (await client.get(f"/organizations/{org['id']}/escalations", headers=_h(token))).json()
    assert listing["total"] == 1 and listing["items"][0]["id"] == str(ticket.id)
    assert (await client.get(f"/organizations/{org['id']}/escalations?status=resolved", headers=_h(token))).json()["total"] == 0
    assert (await client.get(f"/organizations/{org['id']}/escalations?priority=high", headers=_h(token))).json()["total"] == 1
    one = (await client.get(f"/organizations/{org['id']}/escalations/{ticket.id}", headers=_h(token))).json()
    assert one["issue"] == "Cannot find the contract" and one["sla_breached"] is False


async def test_assign_to_a_member_moves_the_ticket_to_assigned_and_rejects_outsiders(client, db_session):
    token, owner, org, ticket = await _org_with_ticket(client, db_session)
    ok = await client.post(f"/organizations/{org['id']}/escalations/{ticket.id}/assign", json={"assignee_id": str(owner.id)}, headers=_h(token))
    assert ok.status_code == 200 and ok.json()["status"] == "assigned" and ok.json()["assignee_id"] == str(owner.id)
    _t2, outsider = await _register(client, db_session, "outsider-esc@example.com")
    bad = await client.post(f"/organizations/{org['id']}/escalations/{ticket.id}/assign", json={"assignee_id": str(outsider.id)}, headers=_h(token))
    assert bad.status_code == 422


async def test_resolving_requires_a_resolution_text_and_stamps_resolved_at(client, db_session):
    token, _owner, org, ticket = await _org_with_ticket(client, db_session)
    url = f"/organizations/{org['id']}/escalations/{ticket.id}"
    assert (await client.patch(url, json={"status": "resolved"}, headers=_h(token))).status_code == 422
    done = await client.patch(url, json={"status": "resolved", "resolution": "Sent the contract by e-mail"}, headers=_h(token))
    assert done.status_code == 200
    body = done.json()
    assert body["status"] == "resolved" and body["resolution"] == "Sent the contract by e-mail" and body["resolved_at"] is not None


async def test_priority_can_be_changed_and_invalid_values_are_rejected(client, db_session):
    token, _owner, org, ticket = await _org_with_ticket(client, db_session)
    url = f"/organizations/{org['id']}/escalations/{ticket.id}"
    assert (await client.patch(url, json={"priority": "low"}, headers=_h(token))).json()["priority"] == "low"
    assert (await client.patch(url, json={"priority": "urgent"}, headers=_h(token))).status_code == 422


async def test_internal_notes(client, db_session):
    token, owner, org, ticket = await _org_with_ticket(client, db_session)
    url = f"/organizations/{org['id']}/escalations/{ticket.id}/notes"
    created = await client.post(url, json={"body": "Called the customer"}, headers=_h(token))
    assert created.status_code == 201 and created.json()["author_id"] == str(owner.id)
    assert (await client.post(url, json={"body": ""}, headers=_h(token))).status_code == 422
    notes = (await client.get(url, headers=_h(token))).json()
    assert [n["body"] for n in notes] == ["Called the customer"]


async def test_sla_breach_is_reported_for_an_overdue_open_ticket_and_in_stats(client, db_session):
    token, _owner, org, ticket = await _org_with_ticket(client, db_session)
    row = await db_session.get(Escalation, ticket.id)
    row.sla_due_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2)
    await db_session.commit()
    one = (await client.get(f"/organizations/{org['id']}/escalations/{ticket.id}", headers=_h(token))).json()
    assert one["sla_breached"] is True
    stats = (await client.get(f"/organizations/{org['id']}/escalations/stats", headers=_h(token))).json()
    assert stats["total"] == 1 and stats["sla_breached"] == 1 and stats["by_priority"] == {"high": 1}


async def test_another_organization_cannot_see_or_touch_the_ticket(client, db_session):
    _token, _owner, org, ticket = await _org_with_ticket(client, db_session)
    other_token, _other = await _register(client, db_session, "other-owner-esc@example.com")
    other_org = (await client.post("/organizations", json={"name": "Other Org"}, headers=_h(other_token))).json()
    # the ticket id of org A used inside org B's URL space: 404, not the data
    r = await client.get(f"/organizations/{other_org['id']}/escalations/{ticket.id}", headers=_h(other_token))
    assert r.status_code == 404
    assert (await client.get(f"/organizations/{other_org['id']}/escalations", headers=_h(other_token))).json()["total"] == 0
    # and org A's URL is closed to a non-member
    assert (await client.get(f"/organizations/{org['id']}/escalations", headers=_h(other_token))).status_code in (403, 404)


async def test_a_plain_member_is_refused(client, db_session):
    token, _owner, org, _ticket = await _org_with_ticket(client, db_session)
    member_token, member = await _register(client, db_session, "member-esc@example.com")
    db_session.add(OrganizationMember(organization_id=uuid.UUID(org["id"]), user_id=member.id, role=OrganizationRole.member))
    await db_session.commit()
    assert (await client.get(f"/organizations/{org['id']}/escalations", headers=_h(member_token))).status_code == 403
    assert token

"""Partie 5.2.9 -- human escalation tool. Fast SQLite suite for
persistence; real httpx.MockTransport for the real email dispatch."""

import uuid

import httpx
import pytest
from sqlalchemy import select

from api.config import settings
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.security.agent_runs import create_run
from api.tools.human_escalation import (
    assign_escalation, escalate_to_human, get_escalation_stats, get_escalations, make_escalation_tool,
    notify_via_webhook, update_escalation_status,
)


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


def _patch_client(monkeypatch, handler):
    monkeypatch.setattr("api.tools.human_escalation._client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)))


# --------------------------------------- escalate_to_human --


async def test_escalate_to_human_creates_a_real_record(db_session):
    """Validation criterion: l'escalade fonctionne."""
    run = await _make_run(db_session)
    escalation = await escalate_to_human(db_session, run.id, "Cannot determine the customer's account", priority="high")
    await db_session.commit()

    assert escalation.status == "open"
    assert escalation.priority == "high"


async def test_escalate_to_human_rejects_an_invalid_priority(db_session):
    run = await _make_run(db_session)
    with pytest.raises(ValueError, match="Invalid priority"):
        await escalate_to_human(db_session, run.id, "issue", priority="urgent-ish")


async def test_escalate_to_human_notifies_real_org_admins_by_email(monkeypatch, db_session, client, register_payload):
    """Validation criterion: les notifications sont envoyées."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Escalation Org")
    org_id = uuid.UUID(org["id"])

    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test_key")
    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json
        sent.append(json.loads(request.read()))
        return httpx.Response(200, json={"id": "email1"})

    _patch_client(monkeypatch, handler)

    run = await _make_run(db_session, organization_id=org_id)
    await escalate_to_human(db_session, run.id, "Stuck on task", priority="critical", organization_id=org_id)
    await db_session.commit()

    assert len(sent) == 1
    assert sent[0]["to"] == [owner.email]
    assert "CRITICAL" in sent[0]["subject"]


async def test_escalate_to_human_survives_a_real_notification_failure(monkeypatch, db_session, client, register_payload):
    """Validation criterion: robustesse -- que se passe-t-il si une
    notification échoue (l'escalade elle-même n'est pas perdue)."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Escalation Fail Org")
    org_id = uuid.UUID(org["id"])

    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test_key")

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network down")

    _patch_client(monkeypatch, handler)

    run = await _make_run(db_session, organization_id=org_id)
    escalation = await escalate_to_human(db_session, run.id, "Stuck", organization_id=org_id)
    await db_session.commit()

    assert escalation.status == "open"  # real record survives even though notification failed


async def test_escalate_to_human_skips_email_without_a_real_configured_key(monkeypatch, db_session, client, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "No Key Org")
    org_id = uuid.UUID(org["id"])
    monkeypatch.setattr(settings, "RESEND_API_KEY", "")

    run = await _make_run(db_session, organization_id=org_id)
    escalation = await escalate_to_human(db_session, run.id, "Stuck", organization_id=org_id)
    assert escalation.status == "open"


# --------------------------------------- get_escalations / stats --


async def test_get_escalations_filters_by_real_status(db_session):
    run = await _make_run(db_session)
    e1 = await escalate_to_human(db_session, run.id, "issue 1")
    e2 = await escalate_to_human(db_session, run.id, "issue 2")
    await update_escalation_status(db_session, e2.id, "resolved", resolution="fixed")
    await db_session.commit()

    open_escalations = await get_escalations(db_session, status="open")
    assert [e.id for e in open_escalations] == [e1.id]


async def test_get_escalation_stats_returns_real_counts(db_session):
    """Validation criterion: les statistiques fonctionnent."""
    run = await _make_run(db_session)
    await escalate_to_human(db_session, run.id, "issue 1", priority="low")
    await escalate_to_human(db_session, run.id, "issue 2", priority="high")
    await db_session.commit()

    stats = await get_escalation_stats(db_session)
    assert stats["total"] == 2
    assert stats["by_status"]["open"] == 2
    assert stats["by_priority"]["low"] == 1
    assert stats["by_priority"]["high"] == 1


# --------------------------------------- update_escalation_status / assign --


async def test_update_escalation_status_records_real_resolution(db_session):
    """Validation criterion: la résolution fonctionne."""
    run = await _make_run(db_session)
    escalation = await escalate_to_human(db_session, run.id, "issue")
    await db_session.commit()

    updated = await update_escalation_status(db_session, escalation.id, "resolved", resolution="Manually handled")
    await db_session.commit()

    assert updated.status == "resolved"
    assert updated.resolution == "Manually handled"
    assert updated.resolved_at is not None


async def test_update_escalation_status_returns_none_for_unknown_id(db_session):
    assert await update_escalation_status(db_session, uuid.uuid4(), "resolved") is None


async def test_assign_escalation_moves_open_to_assigned(db_session):
    """Validation criterion: l'assignation fonctionne."""
    run = await _make_run(db_session)
    escalation = await escalate_to_human(db_session, run.id, "issue")
    await db_session.commit()

    assignee_id = uuid.uuid4()
    assigned = await assign_escalation(db_session, escalation.id, assignee_id)
    await db_session.commit()

    assert assigned.assignee_id == assignee_id
    assert assigned.status == "assigned"


# --------------------------------------- notify_via_webhook --


async def test_notify_via_webhook_posts_real_escalation_data(monkeypatch, db_session):
    run = await _make_run(db_session)
    escalation = await escalate_to_human(db_session, run.id, "issue")
    await db_session.commit()

    posted = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json
        posted.append(json.loads(request.read()))
        return httpx.Response(200)

    _patch_client(monkeypatch, handler)
    await notify_via_webhook("https://hooks.example.com/escalations", escalation)
    assert posted[0]["escalation_id"] == str(escalation.id)


# --------------------------------------- tool wiring --


async def test_escalation_tool_handler_works(db_session):
    run = await _make_run(db_session)
    tool = make_escalation_tool(db_session, run.id, None)
    result = await tool.handler(issue="stuck", priority="high")
    assert "Escalated to a human" in result

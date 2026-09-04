"""Partie 5.1.10 -- human approval. Fast SQLite suite."""

import datetime as dt
import uuid

from sqlalchemy import select

from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.security.agent_runs import create_run
from api.security.human_approval import (
    approve_human_request, check_approval_expired, get_approval_status, get_pending_approvals,
    list_pending_approvals_for_organization, reject_human_request, request_human_approval, requires_human_approval,
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


async def _add_member(db_session, org_id, user_id, role: OrganizationRole, invited_by=None):
    db_session.add(OrganizationMember(organization_id=org_id, user_id=user_id, role=role, invited_by=invited_by))
    await db_session.commit()


async def _make_run(db_session, organization_id=None, agent_id="agent-1"):
    run = await create_run(db_session, agent_id=agent_id, input="do something sensitive", organization_id=organization_id)
    await db_session.commit()
    return run


# --------------------------------------- requires_human_approval --


def test_requires_human_approval_for_a_configured_sensitive_tool():
    assert requires_human_approval("delete_data") is True


def test_requires_human_approval_false_for_a_non_sensitive_tool():
    assert requires_human_approval("calculator") is False


def test_requires_human_approval_false_when_disabled(monkeypatch):
    from api.config import settings
    monkeypatch.setattr(settings, "HUMAN_APPROVAL_ENABLED", False)
    assert requires_human_approval("delete_data") is False


# --------------------------------------- request/approve/reject --


async def test_request_human_approval_creates_a_real_pending_request(db_session):
    """Validation criterion: la demande d'approbation fonctionne."""
    run = await _make_run(db_session)
    user_id = uuid.uuid4()
    approval = await request_human_approval(db_session, run.id, "delete_data", {"target": "doc-1"}, user_id)
    await db_session.commit()

    assert approval.status == "pending"
    assert approval.expires_at > approval.requested_at


async def test_approve_human_request_transitions_to_approved(db_session):
    """Validation criterion: l'approbation fonctionne."""
    run = await _make_run(db_session)
    approval = await request_human_approval(db_session, run.id, "delete_data", {}, uuid.uuid4())
    await db_session.commit()

    approver = uuid.uuid4()
    approved = await approve_human_request(db_session, approval.id, approver, "looks fine")
    await db_session.commit()

    assert approved.status == "approved"
    assert approved.approved_by == approver
    assert approved.comment == "looks fine"


async def test_reject_human_request_transitions_to_rejected(db_session):
    """Validation criterion: le rejet fonctionne."""
    run = await _make_run(db_session)
    approval = await request_human_approval(db_session, run.id, "delete_data", {}, uuid.uuid4())
    await db_session.commit()

    rejected = await reject_human_request(db_session, approval.id, uuid.uuid4(), "not safe")
    await db_session.commit()

    assert rejected.status == "rejected"


async def test_approve_a_nonexistent_request_returns_none(db_session):
    assert await approve_human_request(db_session, uuid.uuid4(), uuid.uuid4()) is None


async def test_approve_an_already_approved_request_is_a_real_no_op(db_session):
    run = await _make_run(db_session)
    approval = await request_human_approval(db_session, run.id, "delete_data", {}, uuid.uuid4())
    await db_session.commit()
    first_approver = uuid.uuid4()
    await approve_human_request(db_session, approval.id, first_approver)
    await db_session.commit()

    second_approver = uuid.uuid4()
    result = await approve_human_request(db_session, approval.id, second_approver)
    await db_session.commit()

    assert result.approved_by == first_approver  # unchanged


# --------------------------------------- expiry --


async def test_check_approval_expired_detects_a_real_expired_request(db_session):
    """Validation criterion: l'expiration fonctionne."""
    run = await _make_run(db_session)
    approval = await request_human_approval(db_session, run.id, "delete_data", {}, uuid.uuid4())
    approval.expires_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)
    await db_session.commit()

    assert await check_approval_expired(db_session, approval.id) is True
    assert await get_approval_status(db_session, approval.id) == "expired"


async def test_check_approval_expired_false_for_a_fresh_request(db_session):
    run = await _make_run(db_session)
    approval = await request_human_approval(db_session, run.id, "delete_data", {}, uuid.uuid4())
    await db_session.commit()

    assert await check_approval_expired(db_session, approval.id) is False


async def test_approve_an_expired_request_is_a_real_no_op(db_session):
    run = await _make_run(db_session)
    approval = await request_human_approval(db_session, run.id, "delete_data", {}, uuid.uuid4())
    approval.expires_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)
    await db_session.commit()

    result = await approve_human_request(db_session, approval.id, uuid.uuid4())
    await db_session.commit()

    assert result.status == "expired"


# --------------------------------------- listing --


async def test_get_pending_approvals_lists_a_users_own_requests(db_session):
    run = await _make_run(db_session)
    requester = uuid.uuid4()
    await request_human_approval(db_session, run.id, "delete_data", {}, requester)
    await request_human_approval(db_session, run.id, "make_payment", {}, uuid.uuid4())
    await db_session.commit()

    pending = await get_pending_approvals(db_session, requester)
    assert len(pending) == 1
    assert pending[0].requested_by == requester


async def test_list_pending_approvals_for_organization_scopes_correctly(db_session):
    """Validation criterion: sécurité -- isolation par organisation."""
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    run_a = await _make_run(db_session, organization_id=org_a)
    await request_human_approval(db_session, run_a.id, "delete_data", {}, uuid.uuid4(), organization_id=org_a)
    await db_session.commit()

    assert len(await list_pending_approvals_for_organization(db_session, org_a)) == 1
    assert len(await list_pending_approvals_for_organization(db_session, org_b)) == 0


# --------------------------------------- endpoints --


async def test_admin_can_approve_a_pending_request(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    org_id = uuid.UUID(org["id"])
    run = await _make_run(db_session, organization_id=org_id)
    approval = await request_human_approval(db_session, run.id, "delete_data", {"doc": "1"}, owner.id, organization_id=org_id)
    await db_session.commit()

    response = await client.post(
        f"/organizations/{org['id']}/approvals/{approval.id}/approve", json={"comment": "ok"}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"


async def test_member_cannot_approve_a_pending_request(client, db_session, register_payload):
    """Validation criterion: sécurité -- les approbations sont
    correctement autorisées."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    org_id = uuid.UUID(org["id"])
    member_token, member = await _register(client, db_session, "member@example.com")
    await _add_member(db_session, org_id, member.id, OrganizationRole.member)

    run = await _make_run(db_session, organization_id=org_id)
    approval = await request_human_approval(db_session, run.id, "delete_data", {}, member.id, organization_id=org_id)
    await db_session.commit()

    response = await client.post(
        f"/organizations/{org['id']}/approvals/{approval.id}/approve", json={}, headers=_auth_header(member_token),
    )
    assert response.status_code == 403


async def test_admin_can_list_pending_approvals(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    org_id = uuid.UUID(org["id"])
    run = await _make_run(db_session, organization_id=org_id)
    await request_human_approval(db_session, run.id, "delete_data", {}, owner.id, organization_id=org_id)
    await db_session.commit()

    response = await client.get(f"/organizations/{org['id']}/approvals/pending", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_get_approval_status_endpoint(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    org_id = uuid.UUID(org["id"])
    run = await _make_run(db_session, organization_id=org_id)
    approval = await request_human_approval(db_session, run.id, "delete_data", {}, owner.id, organization_id=org_id)
    await db_session.commit()

    response = await client.get(f"/organizations/{org['id']}/approvals/{approval.id}", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["status"] == "pending"


async def test_get_unknown_approval_returns_404(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.get(f"/organizations/{org['id']}/approvals/{uuid.uuid4()}", headers=_auth_header(owner_token))
    assert response.status_code == 404

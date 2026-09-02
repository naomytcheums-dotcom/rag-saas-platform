"""
Partie 1.3.6 -- per-organization resource quotas. Fast SQLite suite,
same tier as tests/test_teams.py.
"""

import uuid

from sqlalchemy import select

from api.config import settings
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.organization_quota import OrganizationQuota
from api.models.user import User


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


# ------------------------------------------------------- default quota --

async def test_default_quotas_are_created_with_the_organization(client, db_session, register_payload):
    """Validation criterion: default quotas are created with the org."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    quota = await db_session.scalar(select(OrganizationQuota).where(OrganizationQuota.organization_id == uuid.UUID(org["id"])))
    assert quota is not None
    assert quota.max_users == settings.QUOTA_DEFAULT_MAX_USERS
    assert quota.max_workspaces == settings.QUOTA_DEFAULT_MAX_WORKSPACES
    assert quota.max_teams == settings.QUOTA_DEFAULT_MAX_TEAMS
    assert quota.max_documents == settings.QUOTA_DEFAULT_MAX_DOCUMENTS
    assert quota.max_kb_size_mb == settings.QUOTA_DEFAULT_MAX_KB_SIZE_MB


async def test_the_default_org_created_at_registration_also_gets_a_quota(client, db_session, register_payload):
    """create_organization_with_owner is shared by POST /organizations
    AND registration's auto-default-org -- both paths must get one."""
    _, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    membership = await db_session.scalar(select(OrganizationMember).where(OrganizationMember.user_id == owner.id))
    quota = await db_session.scalar(select(OrganizationQuota).where(OrganizationQuota.organization_id == membership.organization_id))
    assert quota is not None


# ------------------------------------------------------------ max_users --

async def test_a_manager_cannot_invite_past_max_users(client, db_session, register_payload, monkeypatch):
    """Validation criterion: a user cannot exceed max_users."""
    monkeypatch.setattr("api.routers.organization_members.send_organization_member_added_email", lambda *a: None)

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    org_id = uuid.UUID(org["id"])

    quota = await db_session.scalar(select(OrganizationQuota).where(OrganizationQuota.organization_id == org_id))
    quota.max_users = 2  # owner already counts as 1
    await db_session.commit()

    _, second = await _register(client, db_session, "secondmember@example.com")
    ok = await client.post(
        f"/organizations/{org['id']}/members/invite", json={"email": "secondmember@example.com"},
        headers=_auth_header(owner_token),
    )
    assert ok.status_code == 201  # fills the 2nd of 2 slots

    _, third = await _register(client, db_session, "thirdmember@example.com")
    blocked = await client.post(
        f"/organizations/{org['id']}/members/invite", json={"email": "thirdmember@example.com"},
        headers=_auth_header(owner_token),
    )
    assert blocked.status_code == 402
    assert "quota" in blocked.json()["detail"].lower()


async def test_accepting_an_invitation_also_respects_max_users(monkeypatch, client, db_session, register_payload):
    """The email-invitation acceptance path (Partie 1.3.4) must not be a
    loophole around the same max_users limit."""
    captured = {}
    monkeypatch.setattr("api.routers.invitations.send_organization_invitation_email", lambda *a: captured.update(link=a[3]))

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    org_id = uuid.UUID(org["id"])

    quota = await db_session.scalar(select(OrganizationQuota).where(OrganizationQuota.organization_id == org_id))
    quota.max_users = 1  # owner already fills it
    await db_session.commit()

    await client.post(
        f"/organizations/{org['id']}/invitations", json={"email": "wouldbesecond@example.com", "role": "member"},
        headers=_auth_header(owner_token),
    )
    token = captured["link"].split("token=")[1]

    response = await client.post("/invitations/accept", json={
        "token": token, "password": "a-brand-new-password-123", "full_name": "Would Be Second", "accept_terms": True,
    })
    assert response.status_code == 402


# -------------------------------------------------------- max_workspaces --

async def test_a_manager_cannot_create_past_max_workspaces(client, db_session, register_payload):
    """Validation criterion: a Manager cannot create more than max_workspaces workspaces."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    org_id = uuid.UUID(org["id"])

    quota = await db_session.scalar(select(OrganizationQuota).where(OrganizationQuota.organization_id == org_id))
    quota.max_workspaces = 1
    await db_session.commit()

    first = await client.post(f"/organizations/{org['id']}/workspaces", json={"name": "First"}, headers=_auth_header(owner_token))
    assert first.status_code == 201

    second = await client.post(f"/organizations/{org['id']}/workspaces", json={"name": "Second"}, headers=_auth_header(owner_token))
    assert second.status_code == 402


# -------------------------------------------------------------- max_teams --

async def test_a_manager_cannot_create_past_max_teams(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    org_id = uuid.UUID(org["id"])

    quota = await db_session.scalar(select(OrganizationQuota).where(OrganizationQuota.organization_id == org_id))
    quota.max_teams = 1
    await db_session.commit()

    first = await client.post(f"/organizations/{org['id']}/teams", json={"name": "First"}, headers=_auth_header(owner_token))
    assert first.status_code == 201

    second = await client.post(f"/organizations/{org['id']}/teams", json={"name": "Second"}, headers=_auth_header(owner_token))
    assert second.status_code == 402


# ---------------------------------------------------------- GET endpoint --

async def test_admin_can_view_quotas_and_usage(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.post(f"/organizations/{org['id']}/workspaces", json={"name": "Only"}, headers=_auth_header(owner_token))

    admin_token, admin = await _register(client, db_session, "quotaadmin@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin.id, OrganizationRole.admin, invited_by=owner.id)

    response = await client.get(f"/organizations/{org['id']}/quotas", headers=_auth_header(admin_token))
    assert response.status_code == 200
    body = response.json()
    assert body["users"]["used"] == 2  # owner + admin
    assert body["workspaces"]["used"] == 1
    assert body["workspaces"]["limit"] == settings.QUOTA_DEFAULT_MAX_WORKSPACES
    # Not-yet-trackable dimensions report None, not 0 or a fake number.
    assert body["documents"]["used"] is None
    assert body["requests_per_day"]["used"] is None


async def test_manager_cannot_view_quotas(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    manager_token, manager = await _register(client, db_session, "quotamanager@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), manager.id, OrganizationRole.manager, invited_by=owner.id)

    response = await client.get(f"/organizations/{org['id']}/quotas", headers=_auth_header(manager_token))
    assert response.status_code == 403


# -------------------------------------------------------- PATCH endpoint --

async def test_only_owner_can_update_quotas(client, db_session, register_payload):
    """Validation criterion: only Owner can modify quotas."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    admin_token, admin = await _register(client, db_session, "quotapatchadmin@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin.id, OrganizationRole.admin, invited_by=owner.id)

    blocked = await client.patch(
        f"/organizations/{org['id']}/quotas", json={"max_workspaces": 50}, headers=_auth_header(admin_token),
    )
    assert blocked.status_code == 403

    allowed = await client.patch(
        f"/organizations/{org['id']}/quotas", json={"max_workspaces": 50}, headers=_auth_header(owner_token),
    )
    assert allowed.status_code == 200
    assert allowed.json()["workspaces"]["limit"] == 50


async def test_updating_one_field_leaves_others_unchanged(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.patch(
        f"/organizations/{org['id']}/quotas", json={"max_teams": 99}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["teams"]["limit"] == 99
    assert body["users"]["limit"] == settings.QUOTA_DEFAULT_MAX_USERS  # untouched


async def test_raising_a_quota_after_it_was_hit_unblocks_further_use(client, db_session, register_payload):
    """Confirms usage is a live count, not a stale/cached counter --
    raising the limit takes effect immediately on the next check."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    org_id = uuid.UUID(org["id"])

    quota = await db_session.scalar(select(OrganizationQuota).where(OrganizationQuota.organization_id == org_id))
    quota.max_workspaces = 1
    await db_session.commit()

    await client.post(f"/organizations/{org['id']}/workspaces", json={"name": "First"}, headers=_auth_header(owner_token))
    blocked = await client.post(f"/organizations/{org['id']}/workspaces", json={"name": "Second"}, headers=_auth_header(owner_token))
    assert blocked.status_code == 402

    await client.patch(f"/organizations/{org['id']}/quotas", json={"max_workspaces": 2}, headers=_auth_header(owner_token))

    allowed = await client.post(f"/organizations/{org['id']}/workspaces", json={"name": "Second"}, headers=_auth_header(owner_token))
    assert allowed.status_code == 201

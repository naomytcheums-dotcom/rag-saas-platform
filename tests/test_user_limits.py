"""
Partie 1.3.7 -- per-member limits on top of the organization role
hierarchy. Fast SQLite suite, same tier as tests/test_quotas.py.
"""

import uuid

from sqlalchemy import select

from api.models.organization import OrganizationMember, OrganizationRole
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
    membership = OrganizationMember(organization_id=org_id, user_id=user_id, role=role, invited_by=invited_by)
    db_session.add(membership)
    await db_session.commit()
    return membership


async def _get_membership(db_session, org_id, user_id):
    return await db_session.scalar(
        select(OrganizationMember).where(OrganizationMember.organization_id == org_id, OrganizationMember.user_id == user_id)
    )


# ------------------------------------------------------------- defaults --

async def test_new_memberships_get_the_documented_defaults(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    _, member = await _register(client, db_session, "defaultsmember@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member, invited_by=owner.id)

    membership = await _get_membership(db_session, uuid.UUID(org["id"]), member.id)
    assert membership.daily_request_limit is None
    assert membership.max_documents is None
    assert membership.max_conversations is None
    assert membership.can_create_workspaces is True
    assert membership.can_create_teams is True
    assert membership.can_invite_members is False


# -------------------------------------------------- can_create_workspaces --

async def test_a_manager_with_can_create_workspaces_false_is_blocked(client, db_session, register_payload):
    """Validation criterion: a Member (here, a Manager -- the tier that
    would otherwise pass) with can_create_workspaces=False cannot create
    a workspace, despite having sufficient role."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    org_id = uuid.UUID(org["id"])

    manager_token, manager = await _register(client, db_session, "restrictedmanager@example.com")
    membership = await _add_member(db_session, org_id, manager.id, OrganizationRole.manager, invited_by=owner.id)
    membership.can_create_workspaces = False
    await db_session.commit()

    response = await client.post(f"/organizations/{org['id']}/workspaces", json={"name": "Nope"}, headers=_auth_header(manager_token))
    assert response.status_code == 403


async def test_a_manager_with_the_default_flag_can_still_create_workspaces(client, db_session, register_payload):
    """The restrictive flag defaults True -- unrestricted, unchanged
    behavior for anyone who already had the role."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    manager_token, manager = await _register(client, db_session, "defaultmanager@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), manager.id, OrganizationRole.manager, invited_by=owner.id)

    response = await client.post(f"/organizations/{org['id']}/workspaces", json={"name": "Fine"}, headers=_auth_header(manager_token))
    assert response.status_code == 201


async def test_a_plain_member_still_cannot_create_workspaces_regardless_of_the_flag(client, db_session, register_payload):
    """The restrictive flag is never even consulted below Manager -- the
    role gate blocks a plain Member first, same as before this step,
    even though can_create_workspaces defaults True for them too."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    member_token, member = await _register(client, db_session, "stillblockedmember@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.post(f"/organizations/{org['id']}/workspaces", json={"name": "Nope"}, headers=_auth_header(member_token))
    assert response.status_code == 403


# ------------------------------------------------------- can_create_teams --

async def test_a_manager_with_can_create_teams_false_is_blocked(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    org_id = uuid.UUID(org["id"])

    manager_token, manager = await _register(client, db_session, "noteamsmanager@example.com")
    membership = await _add_member(db_session, org_id, manager.id, OrganizationRole.manager, invited_by=owner.id)
    membership.can_create_teams = False
    await db_session.commit()

    response = await client.post(f"/organizations/{org['id']}/teams", json={"name": "Nope"}, headers=_auth_header(manager_token))
    assert response.status_code == 403


# ------------------------------------------------------ can_invite_members --

async def test_a_member_with_can_invite_members_true_can_invite(monkeypatch, client, db_session, register_payload):
    """The additive OR-gate: a plain Member normally cannot invite, but
    can_invite_members=True lets them, without promoting them."""
    monkeypatch.setattr("api.routers.organization_members.send_organization_member_added_email", lambda *a: None)

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    org_id = uuid.UUID(org["id"])

    member_token, member = await _register(client, db_session, "invitermember@example.com")
    membership = await _add_member(db_session, org_id, member.id, OrganizationRole.member, invited_by=owner.id)
    membership.can_invite_members = True
    await db_session.commit()

    _, target = await _register(client, db_session, "invitedbymember@example.com")
    response = await client.post(
        f"/organizations/{org['id']}/members/invite", json={"email": "invitedbymember@example.com"},
        headers=_auth_header(member_token),
    )
    assert response.status_code == 201

    # Still just a Member -- the grant didn't promote them.
    membership_after = await _get_membership(db_session, org_id, member.id)
    assert membership_after.role == OrganizationRole.member


async def test_a_member_with_can_invite_members_true_still_cannot_invite_as_admin(monkeypatch, client, db_session, register_payload):
    """The widened privilege-escalation guard: the additive grant only
    ever allows inviting as member/viewer, same ceiling as a Manager."""
    monkeypatch.setattr("api.routers.organization_members.send_organization_member_added_email", lambda *a: None)

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    org_id = uuid.UUID(org["id"])

    member_token, member = await _register(client, db_session, "escalatingmember@example.com")
    membership = await _add_member(db_session, org_id, member.id, OrganizationRole.member, invited_by=owner.id)
    membership.can_invite_members = True
    await db_session.commit()

    _, target = await _register(client, db_session, "wouldbeadminviamember@example.com")
    response = await client.post(
        f"/organizations/{org['id']}/members/invite", json={"email": "wouldbeadminviamember@example.com", "role": "admin"},
        headers=_auth_header(member_token),
    )
    assert response.status_code == 403


async def test_a_member_without_the_flag_still_cannot_invite(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    member_token, member = await _register(client, db_session, "nonintivermember@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member, invited_by=owner.id)

    _, target = await _register(client, db_session, "notinvited@example.com")
    response = await client.post(
        f"/organizations/{org['id']}/members/invite", json={"email": "notinvited@example.com"},
        headers=_auth_header(member_token),
    )
    assert response.status_code == 403


# --------------------------------------------------------- not-yet-tracked --

async def test_check_user_limit_is_always_true_for_the_three_untracked_dimensions(db_session, client, register_payload):
    from api.security.user_limits import check_user_limit

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    org_id = uuid.UUID(org["id"])

    for resource_type in ("requests_per_day", "documents", "conversations"):
        assert await check_user_limit(db_session, owner.id, org_id, resource_type) is True


# --------------------------------------------------------- GET/PATCH admin --

async def test_admin_can_view_and_update_a_members_limits(client, db_session, register_payload):
    """Validation criterion: an Admin can modify a Member's limits."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    org_id = uuid.UUID(org["id"])

    admin_token, admin = await _register(client, db_session, "limitsadmin@example.com")
    await _add_member(db_session, org_id, admin.id, OrganizationRole.admin, invited_by=owner.id)

    _, member = await _register(client, db_session, "limitedmember@example.com")
    await _add_member(db_session, org_id, member.id, OrganizationRole.member, invited_by=owner.id)

    view = await client.get(f"/organizations/{org['id']}/members/{member.id}/limits", headers=_auth_header(admin_token))
    assert view.status_code == 200
    assert view.json()["limits"]["max_documents"] is None

    update = await client.patch(
        f"/organizations/{org['id']}/members/{member.id}/limits",
        json={"max_documents": 5, "can_create_workspaces": False},
        headers=_auth_header(admin_token),
    )
    assert update.status_code == 200
    assert update.json()["limits"]["max_documents"] == 5
    assert update.json()["limits"]["can_create_workspaces"] is False


async def test_a_member_cannot_modify_their_own_limits(client, db_session, register_payload):
    """Validation criterion: a Member cannot modify their own limits."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    member_token, member = await _register(client, db_session, "selflimiter@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.patch(
        f"/organizations/{org['id']}/members/{member.id}/limits", json={"can_create_workspaces": False},
        headers=_auth_header(member_token),
    )
    assert response.status_code == 403


async def test_manager_cannot_view_or_update_a_members_limits(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    org_id = uuid.UUID(org["id"])

    manager_token, manager = await _register(client, db_session, "limitsmanager@example.com")
    await _add_member(db_session, org_id, manager.id, OrganizationRole.manager, invited_by=owner.id)

    _, member = await _register(client, db_session, "limitedbymanager@example.com")
    await _add_member(db_session, org_id, member.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.get(f"/organizations/{org['id']}/members/{member.id}/limits", headers=_auth_header(manager_token))
    assert response.status_code == 403


async def test_admin_cannot_change_the_owners_limits(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    admin_token, admin = await _register(client, db_session, "cannotchangeowner@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin.id, OrganizationRole.admin, invited_by=owner.id)

    response = await client.patch(
        f"/organizations/{org['id']}/members/{owner.id}/limits", json={"can_create_workspaces": False},
        headers=_auth_header(admin_token),
    )
    assert response.status_code == 400


async def test_clearing_a_numeric_limit_back_to_null(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    org_id = uuid.UUID(org["id"])

    _, member = await _register(client, db_session, "clearlimitmember@example.com")
    membership = await _add_member(db_session, org_id, member.id, OrganizationRole.member, invited_by=owner.id)
    membership.max_documents = 10
    await db_session.commit()

    response = await client.patch(
        f"/organizations/{org['id']}/members/{member.id}/limits", json={"max_documents": None},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    assert response.json()["limits"]["max_documents"] is None


# --------------------------------------------------------------- GET /me --

async def test_get_my_limits_lists_every_organization(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    await _create_org(client, owner_token, "Second Org")  # owner already has a default org from registration

    response = await client.get("/users/me/limits", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert len(response.json()["items"]) == 2
    for entry in response.json()["items"]:
        assert entry["usage"]["documents"] is None
        assert entry["limits"]["can_create_workspaces"] is True

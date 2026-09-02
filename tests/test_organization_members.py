"""
Etape 1.2.3 -- Admin: member-management endpoints. Fast SQLite suite,
same tier as tests/test_organizations.py.
"""

import uuid

from sqlalchemy import select

from api.models.organization import Organization, OrganizationMember, OrganizationRole
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


# ------------------------------------------------------- list members --

async def test_admin_can_list_members(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    admin_token, admin_user = await _register(client, db_session, "admin@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin_user.id, OrganizationRole.admin, invited_by=owner.id)

    response = await client.get(f"/organizations/{org['id']}/members", headers=_auth_header(admin_token))
    assert response.status_code == 200
    emails = {item["email"] for item in response.json()["items"]}
    assert emails == {register_payload["email"], "admin@example.com"}


async def test_a_member_cannot_list_members(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    member_token, member_user = await _register(client, db_session, "member@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member_user.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.get(f"/organizations/{org['id']}/members", headers=_auth_header(member_token))
    assert response.status_code == 403


# ----------------------------------------------------------- invite ----

async def test_admin_can_invite_an_existing_user(monkeypatch, client, db_session, register_payload):
    captured = []
    monkeypatch.setattr("api.routers.organization_members.send_organization_member_added_email", lambda *a: captured.append(a))

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    admin_token, admin_user = await _register(client, db_session, "admin2@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin_user.id, OrganizationRole.admin, invited_by=owner.id)

    _, invitee = await _register(client, db_session, "invitee@example.com")

    response = await client.post(
        f"/organizations/{org['id']}/members/invite", json={"email": "invitee@example.com", "role": "member"},
        headers=_auth_header(admin_token),
    )
    assert response.status_code == 201
    assert response.json()["role"] == "member"
    assert len(captured) == 1

    membership = await db_session.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == uuid.UUID(org["id"]), OrganizationMember.user_id == invitee.id,
        )
    )
    assert membership is not None
    assert membership.invited_by == admin_user.id


async def test_a_member_cannot_invite(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    member_token, member_user = await _register(client, db_session, "plainmember@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member_user.id, OrganizationRole.member, invited_by=owner.id)

    _, someone = await _register(client, db_session, "someone@example.com")

    response = await client.post(
        f"/organizations/{org['id']}/members/invite", json={"email": "someone@example.com"},
        headers=_auth_header(member_token),
    )
    assert response.status_code == 403


async def test_inviting_an_unregistered_email_returns_404(client, db_session, register_payload):
    owner_token, _ = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(
        f"/organizations/{org['id']}/members/invite", json={"email": "nobody@example.com"},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 404


async def test_inviting_an_already_existing_member_returns_409(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(
        f"/organizations/{org['id']}/members/invite", json={"email": register_payload["email"]},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 409


async def test_cannot_invite_someone_as_owner(client, db_session, register_payload):
    owner_token, _ = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await _register(client, db_session, "wouldbeowner@example.com")

    response = await client.post(
        f"/organizations/{org['id']}/members/invite", json={"email": "wouldbeowner@example.com", "role": "owner"},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 422  # rejected by Pydantic validation, never reaches the handler


# ------------------------------------------------------- role update ---

async def test_admin_can_change_a_members_role(monkeypatch, client, db_session, register_payload):
    captured = []
    monkeypatch.setattr("api.routers.organization_members.send_organization_member_role_changed_email", lambda *a: captured.append(a))

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    admin_token, admin_user = await _register(client, db_session, "admin3@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin_user.id, OrganizationRole.admin, invited_by=owner.id)

    _, target = await _register(client, db_session, "promoteme@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), target.id, OrganizationRole.viewer, invited_by=owner.id)

    response = await client.patch(
        f"/organizations/{org['id']}/members/{target.id}/role", json={"role": "manager"},
        headers=_auth_header(admin_token),
    )
    assert response.status_code == 200
    assert response.json()["role"] == "manager"
    assert len(captured) == 1

    membership = await db_session.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == uuid.UUID(org["id"]), OrganizationMember.user_id == target.id,
        )
    )
    assert membership.role == OrganizationRole.manager


async def test_admin_cannot_change_the_owners_role(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    admin_token, admin_user = await _register(client, db_session, "admin4@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin_user.id, OrganizationRole.admin, invited_by=owner.id)

    response = await client.patch(
        f"/organizations/{org['id']}/members/{owner.id}/role", json={"role": "member"},
        headers=_auth_header(admin_token),
    )
    assert response.status_code == 400

    membership = await db_session.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == uuid.UUID(org["id"]), OrganizationMember.user_id == owner.id,
        )
    )
    assert membership.role == OrganizationRole.owner  # unchanged


async def test_a_member_cannot_change_roles(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    member_token, member_user = await _register(client, db_session, "plainmember2@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member_user.id, OrganizationRole.member, invited_by=owner.id)

    _, target = await _register(client, db_session, "target@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), target.id, OrganizationRole.viewer, invited_by=owner.id)

    response = await client.patch(
        f"/organizations/{org['id']}/members/{target.id}/role", json={"role": "admin"},
        headers=_auth_header(member_token),
    )
    assert response.status_code == 403


async def test_cannot_promote_a_member_to_owner_via_role_update(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    _, target = await _register(client, db_session, "wannabeowner@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), target.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.patch(
        f"/organizations/{org['id']}/members/{target.id}/role", json={"role": "owner"},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 422


# ------------------------------------------------------------ remove ---

async def test_admin_can_remove_a_member(monkeypatch, client, db_session, register_payload):
    captured = []
    monkeypatch.setattr("api.routers.organization_members.send_organization_member_removed_email", lambda *a: captured.append(a))

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    admin_token, admin_user = await _register(client, db_session, "admin5@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin_user.id, OrganizationRole.admin, invited_by=owner.id)

    _, target = await _register(client, db_session, "removeme@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), target.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.delete(f"/organizations/{org['id']}/members/{target.id}", headers=_auth_header(admin_token))
    assert response.status_code == 200
    assert len(captured) == 1

    remaining = await db_session.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == uuid.UUID(org["id"]), OrganizationMember.user_id == target.id,
        )
    )
    assert remaining is None


async def test_admin_cannot_remove_the_owner(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    admin_token, admin_user = await _register(client, db_session, "admin6@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin_user.id, OrganizationRole.admin, invited_by=owner.id)

    response = await client.delete(f"/organizations/{org['id']}/members/{owner.id}", headers=_auth_header(admin_token))
    assert response.status_code == 400

    still_there = await db_session.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == uuid.UUID(org["id"]), OrganizationMember.user_id == owner.id,
        )
    )
    assert still_there is not None


async def test_a_member_cannot_remove_members(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    member_token, member_user = await _register(client, db_session, "plainmember3@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member_user.id, OrganizationRole.member, invited_by=owner.id)

    _, target = await _register(client, db_session, "target2@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), target.id, OrganizationRole.viewer, invited_by=owner.id)

    response = await client.delete(f"/organizations/{org['id']}/members/{target.id}", headers=_auth_header(member_token))
    assert response.status_code == 403


# --------------------------------------------------- Admin's own limits

async def test_admin_still_cannot_delete_the_organization(client, db_session, register_payload):
    """Validation criterion: Admin gets member-management, but the
    organization-level Owner-only gate (api/routers/organizations.py)
    is completely unaffected by this step."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    admin_token, admin_user = await _register(client, db_session, "admin7@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin_user.id, OrganizationRole.admin, invited_by=owner.id)

    response = await client.delete(f"/organizations/{org['id']}", headers=_auth_header(admin_token))
    assert response.status_code == 403

    assert await db_session.get(Organization, uuid.UUID(org["id"])) is not None


# ----------------------------------------------- Etape 1.2.4 -- Manager

async def test_manager_can_list_members(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    manager_token, manager_user = await _register(client, db_session, "manager1@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), manager_user.id, OrganizationRole.manager, invited_by=owner.id)

    response = await client.get(f"/organizations/{org['id']}/members", headers=_auth_header(manager_token))
    assert response.status_code == 200


async def test_manager_can_invite_a_member(monkeypatch, client, db_session, register_payload):
    monkeypatch.setattr("api.routers.organization_members.send_organization_member_added_email", lambda *a: None)

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    manager_token, manager_user = await _register(client, db_session, "manager2@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), manager_user.id, OrganizationRole.manager, invited_by=owner.id)

    await _register(client, db_session, "invitedbymanager@example.com")

    response = await client.post(
        f"/organizations/{org['id']}/members/invite", json={"email": "invitedbymanager@example.com", "role": "member"},
        headers=_auth_header(manager_token),
    )
    assert response.status_code == 201
    assert response.json()["role"] == "member"


async def test_manager_can_invite_a_viewer(monkeypatch, client, db_session, register_payload):
    monkeypatch.setattr("api.routers.organization_members.send_organization_member_added_email", lambda *a: None)

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    manager_token, manager_user = await _register(client, db_session, "manager3@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), manager_user.id, OrganizationRole.manager, invited_by=owner.id)

    await _register(client, db_session, "invitedasviewer@example.com")

    response = await client.post(
        f"/organizations/{org['id']}/members/invite", json={"email": "invitedasviewer@example.com", "role": "viewer"},
        headers=_auth_header(manager_token),
    )
    assert response.status_code == 201
    assert response.json()["role"] == "viewer"


async def test_manager_cannot_invite_as_admin(client, db_session, register_payload):
    """The privilege-escalation guard: a Manager could otherwise invite
    someone directly as Admin, handing out a role tier the Manager isn't
    themselves allowed to grant via role-update."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    manager_token, manager_user = await _register(client, db_session, "manager4@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), manager_user.id, OrganizationRole.manager, invited_by=owner.id)

    _, target = await _register(client, db_session, "wouldbeadmin@example.com")

    response = await client.post(
        f"/organizations/{org['id']}/members/invite", json={"email": "wouldbeadmin@example.com", "role": "admin"},
        headers=_auth_header(manager_token),
    )
    assert response.status_code == 403

    membership = await db_session.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == uuid.UUID(org["id"]), OrganizationMember.user_id == target.id,
        )
    )
    assert membership is None  # never added at all, not added as a lower role


async def test_manager_cannot_invite_as_manager(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    manager_token, manager_user = await _register(client, db_session, "manager5@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), manager_user.id, OrganizationRole.manager, invited_by=owner.id)

    await _register(client, db_session, "wouldbemanager@example.com")

    response = await client.post(
        f"/organizations/{org['id']}/members/invite", json={"email": "wouldbemanager@example.com", "role": "manager"},
        headers=_auth_header(manager_token),
    )
    assert response.status_code == 403


async def test_admin_can_still_invite_as_admin(monkeypatch, client, db_session, register_payload):
    """The Manager guard must not accidentally tighten what Admin/Owner
    can already do -- only Manager-issued invites are restricted."""
    monkeypatch.setattr("api.routers.organization_members.send_organization_member_added_email", lambda *a: None)

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    await _register(client, db_session, "wouldbeadminforreal@example.com")

    response = await client.post(
        f"/organizations/{org['id']}/members/invite", json={"email": "wouldbeadminforreal@example.com", "role": "admin"},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 201
    assert response.json()["role"] == "admin"


async def test_manager_cannot_change_a_members_role(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    manager_token, manager_user = await _register(client, db_session, "manager6@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), manager_user.id, OrganizationRole.manager, invited_by=owner.id)

    _, target = await _register(client, db_session, "targetformanager@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), target.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.patch(
        f"/organizations/{org['id']}/members/{target.id}/role", json={"role": "admin"},
        headers=_auth_header(manager_token),
    )
    assert response.status_code == 403


async def test_manager_cannot_remove_a_member(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    manager_token, manager_user = await _register(client, db_session, "manager7@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), manager_user.id, OrganizationRole.manager, invited_by=owner.id)

    _, target = await _register(client, db_session, "targetformanager2@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), target.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.delete(f"/organizations/{org['id']}/members/{target.id}", headers=_auth_header(manager_token))
    assert response.status_code == 403

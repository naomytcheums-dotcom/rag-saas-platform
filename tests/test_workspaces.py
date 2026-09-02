"""
Etape 1.2.4 -- workspace CRUD. Fast SQLite suite, same tier as
tests/test_organizations.py and tests/test_organization_members.py.
"""

import uuid

from sqlalchemy import select

from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.models.workspace import Workspace


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


# ------------------------------------------------------------- create --

async def test_owner_can_create_a_workspace(client, db_session, register_payload):
    owner_token, _ = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(
        f"/organizations/{org['id']}/workspaces", json={"name": "Support KB"}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Support KB"
    assert response.json()["organization_id"] == org["id"]


async def test_manager_can_create_a_workspace(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    manager_token, manager_user = await _register(client, db_session, "wsmanager1@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), manager_user.id, OrganizationRole.manager, invited_by=owner.id)

    response = await client.post(
        f"/organizations/{org['id']}/workspaces", json={"name": "Sales KB"}, headers=_auth_header(manager_token),
    )
    assert response.status_code == 201


async def test_admin_can_create_a_workspace(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    admin_token, admin_user = await _register(client, db_session, "wsadmin1@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin_user.id, OrganizationRole.admin, invited_by=owner.id)

    response = await client.post(
        f"/organizations/{org['id']}/workspaces", json={"name": "Eng KB"}, headers=_auth_header(admin_token),
    )
    assert response.status_code == 201


async def test_member_cannot_create_a_workspace(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    member_token, member_user = await _register(client, db_session, "wsmember1@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member_user.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.post(
        f"/organizations/{org['id']}/workspaces", json={"name": "Nope"}, headers=_auth_header(member_token),
    )
    assert response.status_code == 403


async def test_non_member_gets_404_creating_a_workspace(client, db_session, register_payload):
    owner_token, _ = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    outsider_token, _ = await _register(client, db_session, "outsider1@example.com")

    response = await client.post(
        f"/organizations/{org['id']}/workspaces", json={"name": "Nope"}, headers=_auth_header(outsider_token),
    )
    assert response.status_code == 404


# --------------------------------------------------------------- list --

async def test_member_can_list_workspaces(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.post(f"/organizations/{org['id']}/workspaces", json={"name": "Support KB"}, headers=_auth_header(owner_token))

    member_token, member_user = await _register(client, db_session, "wsmember2@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member_user.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.get(f"/organizations/{org['id']}/workspaces", headers=_auth_header(member_token))
    assert response.status_code == 200
    assert [w["name"] for w in response.json()["items"]] == ["Support KB"]


async def test_viewer_can_list_workspaces(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.post(f"/organizations/{org['id']}/workspaces", json={"name": "Support KB"}, headers=_auth_header(owner_token))

    viewer_token, viewer_user = await _register(client, db_session, "wsviewer1@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer_user.id, OrganizationRole.viewer, invited_by=owner.id)

    response = await client.get(f"/organizations/{org['id']}/workspaces", headers=_auth_header(viewer_token))
    assert response.status_code == 200


async def test_non_member_gets_404_listing_workspaces(client, db_session, register_payload):
    owner_token, _ = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    outsider_token, _ = await _register(client, db_session, "outsider2@example.com")

    response = await client.get(f"/organizations/{org['id']}/workspaces", headers=_auth_header(outsider_token))
    assert response.status_code == 404


# ------------------------------------------------------------- update --

async def test_manager_can_rename_a_workspace(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    workspace = (await client.post(
        f"/organizations/{org['id']}/workspaces", json={"name": "Old Name"}, headers=_auth_header(owner_token),
    )).json()

    manager_token, manager_user = await _register(client, db_session, "wsmanager2@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), manager_user.id, OrganizationRole.manager, invited_by=owner.id)

    response = await client.patch(
        f"/workspaces/{workspace['id']}", json={"name": "New Name"}, headers=_auth_header(manager_token),
    )
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"


async def test_member_cannot_rename_a_workspace(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    workspace = (await client.post(
        f"/organizations/{org['id']}/workspaces", json={"name": "Old Name"}, headers=_auth_header(owner_token),
    )).json()

    member_token, member_user = await _register(client, db_session, "wsmember3@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member_user.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.patch(
        f"/workspaces/{workspace['id']}", json={"name": "New Name"}, headers=_auth_header(member_token),
    )
    assert response.status_code == 403


async def test_non_member_gets_404_renaming_a_workspace(client, db_session, register_payload):
    owner_token, _ = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    workspace = (await client.post(
        f"/organizations/{org['id']}/workspaces", json={"name": "Old Name"}, headers=_auth_header(owner_token),
    )).json()

    outsider_token, _ = await _register(client, db_session, "outsider3@example.com")

    response = await client.patch(
        f"/workspaces/{workspace['id']}", json={"name": "New Name"}, headers=_auth_header(outsider_token),
    )
    assert response.status_code == 404


async def test_renaming_a_nonexistent_workspace_returns_404(client, db_session, register_payload):
    owner_token, _ = await _register(client, db_session, register_payload["email"], register_payload["password"])
    response = await client.patch(
        f"/workspaces/{uuid.uuid4()}", json={"name": "New Name"}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 404


# ------------------------------------------------------------- delete --

async def test_manager_can_delete_a_workspace(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    workspace = (await client.post(
        f"/organizations/{org['id']}/workspaces", json={"name": "To Delete"}, headers=_auth_header(owner_token),
    )).json()

    manager_token, manager_user = await _register(client, db_session, "wsmanager3@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), manager_user.id, OrganizationRole.manager, invited_by=owner.id)

    response = await client.delete(f"/workspaces/{workspace['id']}", headers=_auth_header(manager_token))
    assert response.status_code == 200
    assert await db_session.get(Workspace, uuid.UUID(workspace["id"])) is None


async def test_member_cannot_delete_a_workspace(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    workspace = (await client.post(
        f"/organizations/{org['id']}/workspaces", json={"name": "Stays"}, headers=_auth_header(owner_token),
    )).json()

    member_token, member_user = await _register(client, db_session, "wsmember4@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member_user.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.delete(f"/workspaces/{workspace['id']}", headers=_auth_header(member_token))
    assert response.status_code == 403
    assert await db_session.get(Workspace, uuid.UUID(workspace["id"])) is not None

"""
Etape 1.2.8 -- granular per-resource permissions. Fast SQLite suite,
same tier as tests/test_workspaces.py. Exercises the one real, live
wiring this step ships (api/security/workspaces.py's
require_workspace_permission on PATCH/DELETE /workspaces/{id}) plus the
management endpoints (api/routers/resource_permissions.py) directly.
"""

import datetime as dt
import uuid

from sqlalchemy import select

from api.models.organization import OrganizationMember, OrganizationRole
from api.models.resource_permission import ResourcePermission
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


async def _create_workspace(client, org_id, access_token: str, name: str = "Acme KB") -> dict:
    return (await client.post(
        f"/organizations/{org_id}/workspaces", json={"name": name}, headers=_auth_header(access_token),
    )).json()


# --------------------------------------- live wiring: workspace update --

async def test_viewer_with_granular_grant_can_update_a_workspace(client, db_session, register_payload):
    """Validation criterion: a Viewer with a granular permission can do
    something normally forbidden by their role alone."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    workspace = await _create_workspace(client, org["id"], owner_token)

    viewer_token, viewer = await _register(client, db_session, "grantedviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    grant = await client.post(
        f"/resources/workspace/{workspace['id']}/permissions", json={"user_id": str(viewer.id), "action": "update"},
        headers=_auth_header(owner_token),
    )
    assert grant.status_code == 201

    response = await client.patch(
        f"/workspaces/{workspace['id']}", json={"name": "Renamed by Viewer"}, headers=_auth_header(viewer_token),
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed by Viewer"


async def test_viewer_without_grant_still_cannot_update_a_workspace(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    workspace = await _create_workspace(client, org["id"], owner_token)

    viewer_token, viewer = await _register(client, db_session, "ungrantedviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    response = await client.patch(
        f"/workspaces/{workspace['id']}", json={"name": "Should Fail"}, headers=_auth_header(viewer_token),
    )
    assert response.status_code == 403


async def test_a_grant_for_update_does_not_also_allow_delete(client, db_session, register_payload):
    """Vision critique: an 'update' grant must not implicitly carry 'delete'."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    workspace = await _create_workspace(client, org["id"], owner_token)

    viewer_token, viewer = await _register(client, db_session, "updateonlyviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    await client.post(
        f"/resources/workspace/{workspace['id']}/permissions", json={"user_id": str(viewer.id), "action": "update"},
        headers=_auth_header(owner_token),
    )

    response = await client.delete(f"/workspaces/{workspace['id']}", headers=_auth_header(viewer_token))
    assert response.status_code == 403


async def test_revoking_a_permission_removes_access_immediately(client, db_session, register_payload):
    """Validation criterion: a Member with a revoked permission loses access."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    workspace = await _create_workspace(client, org["id"], owner_token)

    member_token, member = await _register(client, db_session, "revokedmember@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member, invited_by=owner.id)

    await client.post(
        f"/resources/workspace/{workspace['id']}/permissions", json={"user_id": str(member.id), "action": "update"},
        headers=_auth_header(owner_token),
    )
    ok = await client.patch(f"/workspaces/{workspace['id']}", json={"name": "First rename"}, headers=_auth_header(member_token))
    assert ok.status_code == 200

    revoke = await client.delete(
        f"/resources/workspace/{workspace['id']}/permissions/{member.id}/update", headers=_auth_header(owner_token),
    )
    assert revoke.status_code == 200

    blocked = await client.patch(
        f"/workspaces/{workspace['id']}", json={"name": "Second rename"}, headers=_auth_header(member_token),
    )
    assert blocked.status_code == 403


async def test_an_expired_permission_no_longer_grants_access(client, db_session, register_payload):
    """Validation criterion: expired permissions are ignored."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    workspace = await _create_workspace(client, org["id"], owner_token)

    viewer_token, viewer = await _register(client, db_session, "expiredviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    db_session.add(ResourcePermission(
        organization_id=uuid.UUID(org["id"]), resource_type="workspace", resource_id=uuid.UUID(workspace["id"]),
        user_id=viewer.id, action="update", granted_by=owner.id,
        expires_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1),
    ))
    await db_session.commit()

    response = await client.patch(
        f"/workspaces/{workspace['id']}", json={"name": "Should still fail"}, headers=_auth_header(viewer_token),
    )
    assert response.status_code == 403


async def test_a_non_expired_permission_still_works(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    workspace = await _create_workspace(client, org["id"], owner_token)

    viewer_token, viewer = await _register(client, db_session, "futureviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    await client.post(
        f"/resources/workspace/{workspace['id']}/permissions",
        json={"user_id": str(viewer.id), "action": "update", "expires_at": "2099-01-01T00:00:00Z"},
        headers=_auth_header(owner_token),
    )

    response = await client.patch(
        f"/workspaces/{workspace['id']}", json={"name": "Still allowed"}, headers=_auth_header(viewer_token),
    )
    assert response.status_code == 200


# ----------------------------------------------------- grant endpoint --

async def test_manager_cannot_grant_permissions(client, db_session, register_payload):
    """The grant/list/revoke endpoints are Admin+, not Manager+ --
    same anti-enumeration 404 as every other org-admin-gated endpoint."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    workspace = await _create_workspace(client, org["id"], owner_token)

    manager_token, manager = await _register(client, db_session, "grantmanager@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), manager.id, OrganizationRole.manager, invited_by=owner.id)

    _, someone = await _register(client, db_session, "grantee@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), someone.id, OrganizationRole.viewer, invited_by=owner.id)

    response = await client.post(
        f"/resources/workspace/{workspace['id']}/permissions", json={"user_id": str(someone.id), "action": "update"},
        headers=_auth_header(manager_token),
    )
    assert response.status_code == 404


async def test_non_member_gets_404_on_the_grant_endpoint(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    workspace = await _create_workspace(client, org["id"], owner_token)

    outsider_token, _ = await _register(client, db_session, "outsider@example.com")
    _, someone = await _register(client, db_session, "grantee2@example.com")

    response = await client.post(
        f"/resources/workspace/{workspace['id']}/permissions", json={"user_id": str(someone.id), "action": "update"},
        headers=_auth_header(outsider_token),
    )
    assert response.status_code == 404


async def test_cannot_grant_to_a_non_member_of_the_organization(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    workspace = await _create_workspace(client, org["id"], owner_token)

    _, outsider = await _register(client, db_session, "notamember@example.com")

    response = await client.post(
        f"/resources/workspace/{workspace['id']}/permissions", json={"user_id": str(outsider.id), "action": "update"},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 400


async def test_cannot_grant_a_permission_to_yourself(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    workspace = await _create_workspace(client, org["id"], owner_token)

    response = await client.post(
        f"/resources/workspace/{workspace['id']}/permissions", json={"user_id": str(owner.id), "action": "update"},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 400


async def test_admin_cannot_grant_organization_delete_because_admin_lacks_it_themselves(client, db_session, register_payload):
    """Explicit validation criterion: a user cannot grant a permission
    they do not have themselves. organization:delete is Owner-only
    (unchanged since Etape 1.2.2) -- an Admin passes this endpoint's own
    Admin+ gate but still lacks the underlying permission being granted."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    admin_token, admin = await _register(client, db_session, "grantadmin@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin.id, OrganizationRole.admin, invited_by=owner.id)

    _, target = await _register(client, db_session, "wouldbedeleter@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), target.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.post(
        f"/resources/organization/{org['id']}/permissions", json={"user_id": str(target.id), "action": "delete"},
        headers=_auth_header(admin_token),
    )
    assert response.status_code == 403

    remaining = await db_session.scalar(
        select(ResourcePermission).where(
            ResourcePermission.resource_type == "organization", ResourcePermission.resource_id == uuid.UUID(org["id"]),
            ResourcePermission.user_id == target.id,
        )
    )
    assert remaining is None


async def test_owner_can_grant_organization_delete_since_owner_has_it(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    _, target = await _register(client, db_session, "trustedadmin@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), target.id, OrganizationRole.admin, invited_by=owner.id)

    response = await client.post(
        f"/resources/organization/{org['id']}/permissions", json={"user_id": str(target.id), "action": "delete"},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 201


async def test_granting_an_unsupported_action_is_rejected(client, db_session, register_payload):
    """'configure' is in the spec's resource/action table but has no
    real enforcement point on workspaces yet -- rejected as dead data,
    not silently accepted."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    workspace = await _create_workspace(client, org["id"], owner_token)

    _, target = await _register(client, db_session, "configuretarget@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), target.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.post(
        f"/resources/workspace/{workspace['id']}/permissions", json={"user_id": str(target.id), "action": "configure"},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 400


async def test_granting_on_an_unsupported_resource_type_is_rejected(client, db_session, register_payload):
    """'document' doesn't exist as a real table yet (Parties 2/3) --
    a random UUID as resource_id is enough to prove the type itself is
    rejected, independent of whether any specific id exists."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    _, target = await _register(client, db_session, "doctarget@example.com")

    response = await client.post(
        f"/resources/document/{uuid.uuid4()}/permissions", json={"user_id": str(target.id), "action": "read"},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 400


async def test_revoking_a_nonexistent_permission_returns_404(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    workspace = await _create_workspace(client, org["id"], owner_token)

    response = await client.delete(
        f"/resources/workspace/{workspace['id']}/permissions/{uuid.uuid4()}/update", headers=_auth_header(owner_token),
    )
    assert response.status_code == 404


# ---------------------------------------------------------- listing ----

async def test_admin_can_list_permissions_on_a_resource(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    workspace = await _create_workspace(client, org["id"], owner_token)

    _, viewer = await _register(client, db_session, "listedviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)
    await client.post(
        f"/resources/workspace/{workspace['id']}/permissions", json={"user_id": str(viewer.id), "action": "update"},
        headers=_auth_header(owner_token),
    )

    response = await client.get(f"/resources/workspace/{workspace['id']}/permissions", headers=_auth_header(owner_token))
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["user_id"] == str(viewer.id)
    assert items[0]["action"] == "update"
    assert items[0]["is_expired"] is False


async def test_expired_permissions_are_listed_but_marked_expired(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    workspace = await _create_workspace(client, org["id"], owner_token)

    _, viewer = await _register(client, db_session, "expiredlistviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)
    db_session.add(ResourcePermission(
        organization_id=uuid.UUID(org["id"]), resource_type="workspace", resource_id=uuid.UUID(workspace["id"]),
        user_id=viewer.id, action="update", granted_by=owner.id,
        expires_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1),
    ))
    await db_session.commit()

    response = await client.get(f"/resources/workspace/{workspace['id']}/permissions", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["items"][0]["is_expired"] is True


async def test_users_me_permissions_returns_only_the_callers_own_grants(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    workspace = await _create_workspace(client, org["id"], owner_token)

    viewer_token, viewer = await _register(client, db_session, "meviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)
    _, otherviewer = await _register(client, db_session, "otherviewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), otherviewer.id, OrganizationRole.viewer, invited_by=owner.id)

    await client.post(
        f"/resources/workspace/{workspace['id']}/permissions", json={"user_id": str(viewer.id), "action": "update"},
        headers=_auth_header(owner_token),
    )
    await client.post(
        f"/resources/workspace/{workspace['id']}/permissions", json={"user_id": str(otherviewer.id), "action": "update"},
        headers=_auth_header(owner_token),
    )

    response = await client.get("/users/me/permissions", headers=_auth_header(viewer_token))
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["user_id"] == str(viewer.id)

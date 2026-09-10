"""Partie 10.1 -- custom roles & granular permissions."""

import pytest

from api.services.rbac_custom import (
    DuplicateRoleNameError,
    assign_permissions_to_role,
    assign_role_to_user,
    check_permission,
    create_custom_role,
    delete_custom_role,
    get_user_effective_permissions,
    list_permissions,
    remove_permission_from_role,
    remove_role_from_user,
)


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _make_org_with_second_member(client, db_session, register_payload):
    from sqlalchemy import select

    from api.models.organization import OrganizationRole
    from api.models.user import User
    from api.security.organizations import create_organization_with_owner

    owner_token = (await client.post("/auth/register", json=register_payload)).json()["access_token"]
    owner = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    org = await create_organization_with_owner(db_session, name="RBAC Org", owner_user_id=owner.id)
    await db_session.commit()

    member_payload = {"email": "member@example.com", "password": "correct-horse-battery-staple", "accept_terms": True}
    member_token = (await client.post("/auth/register", json=member_payload)).json()["access_token"]
    member = await db_session.scalar(select(User).where(User.email == member_payload["email"]))

    from api.models.organization import OrganizationMember

    db_session.add(OrganizationMember(organization_id=org.id, user_id=member.id, role=OrganizationRole.member))
    await db_session.commit()
    return owner_token, org.id, member.id


async def test_list_permissions_seeds_catalog_once(db_session):
    first = await list_permissions(db_session)
    second = await list_permissions(db_session)
    assert len(first) == 52  # 13 resources x 4 actions
    assert len(second) == 52


async def test_create_custom_role_rejects_duplicate_name(db_session):
    from sqlalchemy import select

    from api.models.organization import OrganizationRole
    from api.models.user import User
    from api.security.organizations import create_organization_with_owner

    user = User(email="owner1@example.com", hashed_password="x", is_active=True)
    db_session.add(user)
    await db_session.flush()
    org = await create_organization_with_owner(db_session, name="Org1", owner_user_id=user.id)
    await db_session.commit()

    await create_custom_role(db_session, organization_id=org.id, name="Support agent", description=None, user_id=user.id)
    await db_session.commit()
    with pytest.raises(DuplicateRoleNameError):
        await create_custom_role(db_session, organization_id=org.id, name="Support agent", description=None, user_id=user.id)


async def test_effective_permissions_union_of_assigned_roles(db_session):
    from api.models.user import User
    from api.security.organizations import create_organization_with_owner

    owner = User(email="owner2@example.com", hashed_password="x", is_active=True)
    member = User(email="member2@example.com", hashed_password="x", is_active=True)
    db_session.add_all([owner, member])
    await db_session.flush()
    org = await create_organization_with_owner(db_session, name="Org2", owner_user_id=owner.id)
    await db_session.commit()

    permissions = await list_permissions(db_session)
    doc_read = next(p for p in permissions if p.key == "documents:read")
    webhook_manage = next(p for p in permissions if p.key == "webhooks:manage")

    role = await create_custom_role(db_session, organization_id=org.id, name="Support", description=None, user_id=owner.id)
    await assign_permissions_to_role(db_session, role_id=role.id, organization_id=org.id, permission_ids=[doc_read.id, webhook_manage.id])
    await assign_role_to_user(db_session, user_id=member.id, role_id=role.id, organization_id=org.id, assigned_by=owner.id)
    await db_session.commit()

    effective = await get_user_effective_permissions(db_session, user_id=member.id, organization_id=org.id)
    assert "documents:read" in effective
    # webhooks:manage implies read/write/delete on the same resource
    assert {"webhooks:manage", "webhooks:read", "webhooks:write", "webhooks:delete"}.issubset(effective)
    assert "agents:read" not in effective

    assert await check_permission(db_session, user_id=member.id, organization_id=org.id, resource="documents", action="read")
    assert not await check_permission(db_session, user_id=member.id, organization_id=org.id, resource="agents", action="read")


async def test_removing_permission_and_role_revokes_access(db_session):
    from api.models.user import User
    from api.security.organizations import create_organization_with_owner

    owner = User(email="owner3@example.com", hashed_password="x", is_active=True)
    member = User(email="member3@example.com", hashed_password="x", is_active=True)
    db_session.add_all([owner, member])
    await db_session.flush()
    org = await create_organization_with_owner(db_session, name="Org3", owner_user_id=owner.id)
    await db_session.commit()

    permissions = await list_permissions(db_session)
    doc_read = next(p for p in permissions if p.key == "documents:read")
    role = await create_custom_role(db_session, organization_id=org.id, name="Reader", description=None, user_id=owner.id)
    await assign_permissions_to_role(db_session, role_id=role.id, organization_id=org.id, permission_ids=[doc_read.id])
    await assign_role_to_user(db_session, user_id=member.id, role_id=role.id, organization_id=org.id, assigned_by=owner.id)
    await db_session.commit()
    assert await check_permission(db_session, user_id=member.id, organization_id=org.id, resource="documents", action="read")

    await remove_permission_from_role(db_session, role_id=role.id, organization_id=org.id, permission_id=doc_read.id)
    await db_session.commit()
    assert not await check_permission(db_session, user_id=member.id, organization_id=org.id, resource="documents", action="read")

    await remove_role_from_user(db_session, user_id=member.id, role_id=role.id)
    await delete_custom_role(db_session, role_id=role.id, organization_id=org.id)
    await db_session.commit()


async def test_rbac_endpoints_gate_on_org_admin(client, db_session, register_payload):
    owner_token, org_id, member_id = await _make_org_with_second_member(client, db_session, register_payload)

    create_response = await client.post(
        f"/organizations/{org_id}/rbac/roles", json={"name": "Support", "description": "handles tickets"},
        headers=_auth_header(owner_token),
    )
    assert create_response.status_code == 201
    role_id = create_response.json()["id"]

    permissions = (await client.get(f"/organizations/{org_id}/rbac/permissions", headers=_auth_header(owner_token))).json()
    doc_read_id = next(p["id"] for p in permissions if p["key"] == "documents:read")

    assign_response = await client.post(
        f"/organizations/{org_id}/rbac/roles/{role_id}/permissions", json={"permission_ids": [doc_read_id]}, headers=_auth_header(owner_token),
    )
    assert assign_response.status_code == 200
    assert "documents:read" in assign_response.json()["permission_keys"]

    await client.post(f"/organizations/{org_id}/rbac/users/{member_id}/roles", json={"role_id": role_id}, headers=_auth_header(owner_token))

    effective = await client.get(f"/organizations/{org_id}/rbac/users/{member_id}/permissions", headers=_auth_header(owner_token))
    assert effective.status_code == 200
    assert "documents:read" in effective.json()["permissions"]

    check_response = await client.post("/rbac/check", json={"organization_id": str(org_id), "resource": "documents", "action": "read"}, headers=_auth_header(owner_token))
    assert check_response.json()["allowed"] is True  # owner always allowed


async def test_rbac_roles_endpoint_rejects_plain_member(client, db_session, register_payload):
    _, org_id, member_id = await _make_org_with_second_member(client, db_session, register_payload)
    from sqlalchemy import select

    from api.models.user import User

    member = await db_session.get(User, member_id)
    login = await client.post("/auth/login", json={"email": member.email, "password": "correct-horse-battery-staple"})
    member_token = login.json()["access_token"]

    response = await client.get(f"/organizations/{org_id}/rbac/roles", headers=_auth_header(member_token))
    assert response.status_code == 403

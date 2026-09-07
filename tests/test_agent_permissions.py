"""Partie 5.3.7 -- agent permissions. Fast SQLite suite."""

import uuid

import pytest
from sqlalchemy import select

from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.security.agents import create_agent, update_agent
from api.services.agent_permissions import (
    AgentPermissionError, add_allowed_user, check_agent_permission, get_allowed_users, remove_allowed_user,
    set_agent_visibility, validate_allowed_roles,
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
    member = OrganizationMember(organization_id=org_id, user_id=user_id, role=role, invited_by=invited_by)
    db_session.add(member)
    await db_session.commit()
    return member


# --------------------------------------- validate_allowed_roles --


def test_validate_allowed_roles_accepts_real_rbac_roles():
    """Validation criterion: cohérence -- réutilise le vrai vocabulaire RBAC."""
    validate_allowed_roles(["member", "viewer"])


def test_validate_allowed_roles_rejects_an_unknown_role():
    with pytest.raises(AgentPermissionError, match="Unknown organization role"):
        validate_allowed_roles(["superadmin"])


# --------------------------------------- check_agent_permission (allow/deny/inheritance) --


async def test_check_agent_permission_rejects_an_unknown_action(db_session):
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()
    with pytest.raises(AgentPermissionError, match="Unknown action"):
        await check_agent_permission(db_session, agent.id, uuid.uuid4(), "fly")


async def test_owner_can_always_use_update_delete_regardless_of_acl(db_session):
    """Validation criterion: héritage -- le rôle RBAC prime toujours pour update/delete."""
    org_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    db_session.add(User(id=owner_id, email="owner@example.com", hashed_password="x", full_name="Owner"))
    await db_session.commit()
    await _add_member(db_session, org_id, owner_id, OrganizationRole.owner)
    agent = await create_agent(db_session, org_id, {"name": "Bot"}, None)
    await db_session.commit()

    for action in ("use", "update", "delete"):
        assert await check_agent_permission(db_session, agent.id, owner_id, action) is True


async def test_member_without_acl_entry_cannot_use_a_private_agent(db_session):
    """Validation criterion: deny -- un member non listé est refusé sur un agent privé."""
    org_id = uuid.uuid4()
    member_id = uuid.uuid4()
    db_session.add(User(id=member_id, email="member@example.com", hashed_password="x", full_name="Member"))
    await db_session.commit()
    await _add_member(db_session, org_id, member_id, OrganizationRole.member)
    agent = await create_agent(db_session, org_id, {"name": "Bot"}, None)
    await db_session.commit()

    assert await check_agent_permission(db_session, agent.id, member_id, "use") is False


async def test_member_cannot_update_or_delete_even_if_allowed_user(db_session):
    """Validation criterion: héritage -- l'ACL n'accorde jamais update/delete."""
    org_id = uuid.uuid4()
    member_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    db_session.add(User(id=member_id, email="member@example.com", hashed_password="x", full_name="Member"))
    db_session.add(User(id=owner_id, email="owner@example.com", hashed_password="x", full_name="Owner"))
    await db_session.commit()
    await _add_member(db_session, org_id, member_id, OrganizationRole.member)
    await _add_member(db_session, org_id, owner_id, OrganizationRole.owner)
    agent = await create_agent(db_session, org_id, {"name": "Bot"}, None)
    await db_session.commit()
    await add_allowed_user(db_session, agent.id, member_id, owner_id)
    await db_session.commit()

    assert await check_agent_permission(db_session, agent.id, member_id, "use") is True
    assert await check_agent_permission(db_session, agent.id, member_id, "update") is False
    assert await check_agent_permission(db_session, agent.id, member_id, "delete") is False


async def test_member_can_use_a_public_agent(db_session):
    """Validation criterion: allow -- is_public ouvre l'accès à tout membre."""
    org_id = uuid.uuid4()
    member_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    db_session.add(User(id=member_id, email="member@example.com", hashed_password="x", full_name="Member"))
    db_session.add(User(id=owner_id, email="owner@example.com", hashed_password="x", full_name="Owner"))
    await db_session.commit()
    await _add_member(db_session, org_id, member_id, OrganizationRole.member)
    await _add_member(db_session, org_id, owner_id, OrganizationRole.owner)
    agent = await create_agent(db_session, org_id, {"name": "Bot"}, None)
    await db_session.commit()
    await set_agent_visibility(db_session, agent.id, True)
    await db_session.commit()

    assert await check_agent_permission(db_session, agent.id, member_id, "use") is True


async def test_member_can_use_agent_via_allowed_roles(db_session):
    """Validation criterion: allow -- héritage via allowed_roles."""
    org_id = uuid.uuid4()
    member_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    db_session.add(User(id=member_id, email="member@example.com", hashed_password="x", full_name="Member"))
    db_session.add(User(id=owner_id, email="owner@example.com", hashed_password="x", full_name="Owner"))
    await db_session.commit()
    await _add_member(db_session, org_id, member_id, OrganizationRole.member)
    await _add_member(db_session, org_id, owner_id, OrganizationRole.owner)
    agent = await create_agent(db_session, org_id, {"name": "Bot"}, None)
    await db_session.commit()
    await set_agent_visibility(db_session, agent.id, False, allowed_roles=["member"])
    await db_session.commit()

    assert await check_agent_permission(db_session, agent.id, member_id, "use") is True


async def test_check_agent_permission_denies_a_non_member(db_session):
    """Validation criterion: deny -- un non-membre de l'organisation est toujours refusé."""
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()
    assert await check_agent_permission(db_session, agent.id, uuid.uuid4(), "use") is False


async def test_check_agent_permission_returns_false_for_unknown_agent(db_session):
    assert await check_agent_permission(db_session, uuid.uuid4(), uuid.uuid4(), "use") is False


# --------------------------------------- add/remove_allowed_user --


async def test_add_allowed_user_is_idempotent(db_session):
    """Validation criterion: cohérence -- ajouter deux fois ne duplique pas."""
    org_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    target_id = uuid.uuid4()
    db_session.add(User(id=owner_id, email="owner@example.com", hashed_password="x", full_name="Owner"))
    await db_session.commit()
    await _add_member(db_session, org_id, owner_id, OrganizationRole.owner)
    agent = await create_agent(db_session, org_id, {"name": "Bot"}, None)
    await db_session.commit()

    await add_allowed_user(db_session, agent.id, target_id, owner_id)
    await add_allowed_user(db_session, agent.id, target_id, owner_id)
    await db_session.commit()

    assert await get_allowed_users(db_session, agent.id) == [str(target_id)]


async def test_add_allowed_user_rejects_a_cross_organization_added_by(db_session):
    """Validation criterion: sécurité -- added_by doit appartenir à l'organisation de l'agent."""
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()
    with pytest.raises(AgentPermissionError):
        await add_allowed_user(db_session, agent.id, uuid.uuid4(), uuid.uuid4())


async def test_remove_allowed_user_is_idempotent_and_real(db_session):
    """Validation criterion: cohérence -- retirer fonctionne et est idempotent."""
    org_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    target_id = uuid.uuid4()
    db_session.add(User(id=owner_id, email="owner@example.com", hashed_password="x", full_name="Owner"))
    await db_session.commit()
    await _add_member(db_session, org_id, owner_id, OrganizationRole.owner)
    agent = await create_agent(db_session, org_id, {"name": "Bot"}, None)
    await db_session.commit()
    await add_allowed_user(db_session, agent.id, target_id, owner_id)
    await db_session.commit()

    await remove_allowed_user(db_session, agent.id, target_id, owner_id)
    await remove_allowed_user(db_session, agent.id, target_id, owner_id)
    await db_session.commit()

    assert await get_allowed_users(db_session, agent.id) == []


async def test_update_agent_rejects_an_unknown_allowed_role_via_generic_update(db_session):
    """Validation criterion: sécurité -- pas de contournement via l'endpoint générique."""
    agent = await create_agent(db_session, uuid.uuid4(), {"name": "Bot"}, None)
    await db_session.commit()
    with pytest.raises(AgentPermissionError):
        await update_agent(db_session, agent.id, {"allowed_roles": ["superadmin"]})


# --------------------------------------- endpoints --


async def test_manager_can_update_agent_permissions(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]

    response = await client.patch(f"/agents/{agent_id}/permissions", json={"is_public": True}, headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["is_public"] is True


async def test_member_cannot_read_or_update_agent_permissions(client, db_session, register_payload):
    """Validation criterion: sécurité -- les permissions RBAC existantes sont respectées."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]
    member_token, member = await _register(client, db_session, "member@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member)

    get_response = await client.get(f"/agents/{agent_id}/permissions", headers=_auth_header(member_token))
    assert get_response.status_code == 403
    patch_response = await client.patch(f"/agents/{agent_id}/permissions", json={"is_public": True}, headers=_auth_header(member_token))
    assert patch_response.status_code == 403


async def test_add_and_remove_allowed_user_endpoints(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]
    member_token, member = await _register(client, db_session, "member@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member)

    add_response = await client.post(
        f"/agents/{agent_id}/permissions/users", json={"user_id": str(member.id)}, headers=_auth_header(owner_token),
    )
    assert add_response.status_code == 200
    assert add_response.json()["allowed_users"] == [str(member.id)]

    remove_response = await client.delete(f"/agents/{agent_id}/permissions/users/{member.id}", headers=_auth_header(owner_token))
    assert remove_response.status_code == 200
    assert remove_response.json()["allowed_users"] == []


async def test_get_agent_permissions_endpoint(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/agents", json={"name": "Bot"}, headers=_auth_header(owner_token))
    agent_id = created.json()["id"]

    response = await client.get(f"/agents/{agent_id}/permissions", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert response.json() == {"is_public": False, "allowed_roles": [], "allowed_users": []}


async def test_create_agent_rejects_an_unknown_allowed_role(client, db_session, register_payload):
    """Validation criterion: sécurité -- create_agent lui-même est protégé."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(
        f"/organizations/{org['id']}/agents", json={"name": "Bot", "allowed_roles": ["superadmin"]}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 400

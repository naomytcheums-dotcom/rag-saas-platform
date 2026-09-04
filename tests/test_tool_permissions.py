"""Partie 5.1.3 -- tool permissions. Fast SQLite suite, same tier as
tests/test_resource_permissions.py."""

import uuid

import pytest
from sqlalchemy import select

from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.security.tool_permissions import (
    check_tool_permission, get_available_tools, get_tool_permissions, grant_tool_permission, revoke_tool_permission,
)
from api.services.tools import CALCULATOR_TOOL


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


# --------------------------------------- security-layer: precedence --


async def test_check_tool_permission_defaults_to_allow(db_session):
    """Validation criterion: robustesse -- default-allow when nothing
    is configured."""
    org_id = uuid.uuid4()
    assert await check_tool_permission(db_session, org_id, "agent-1", uuid.uuid4(), "calculator") == "allow"


async def test_grant_and_check_an_organization_wide_deny(db_session):
    org_id = uuid.uuid4()
    await grant_tool_permission(db_session, org_id, None, None, "calculator", "deny", granted_by=None)
    await db_session.commit()

    assert await check_tool_permission(db_session, org_id, "any-agent", uuid.uuid4(), "calculator") == "deny"


async def test_a_user_specific_allow_overrides_an_agent_wide_deny(db_session):
    """Validation criterion: cohérence -- l'héritage/priorité fonctionne
    (le plus spécifique gagne)."""
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    await grant_tool_permission(db_session, org_id, "agent-1", None, "calculator", "deny", granted_by=None)
    await grant_tool_permission(db_session, org_id, "agent-1", user_id, "calculator", "allow", granted_by=None)
    await db_session.commit()

    assert await check_tool_permission(db_session, org_id, "agent-1", user_id, "calculator") == "allow"
    other_user = uuid.uuid4()
    assert await check_tool_permission(db_session, org_id, "agent-1", other_user, "calculator") == "deny"


async def test_permissions_are_scoped_per_organization(db_session):
    """Validation criterion: sécurité -- une organisation ne peut pas
    affecter les permissions d'une autre."""
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    await grant_tool_permission(db_session, org_a, None, None, "calculator", "deny", granted_by=None)
    await db_session.commit()

    assert await check_tool_permission(db_session, org_a, "agent-1", uuid.uuid4(), "calculator") == "deny"
    assert await check_tool_permission(db_session, org_b, "agent-1", uuid.uuid4(), "calculator") == "allow"


async def test_grant_tool_permission_upserts_rather_than_duplicating(db_session):
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    await grant_tool_permission(db_session, org_id, "agent-1", user_id, "calculator", "deny", granted_by=None)
    await grant_tool_permission(db_session, org_id, "agent-1", user_id, "calculator", "allow", granted_by=None)
    await db_session.commit()

    rows = await get_tool_permissions(db_session, org_id, agent_id="agent-1")
    assert len(rows) == 1
    assert rows[0].permission == "allow"


async def test_grant_tool_permission_rejects_an_invalid_value(db_session):
    with pytest.raises(ValueError):
        await grant_tool_permission(db_session, uuid.uuid4(), "agent-1", None, "calculator", "maybe", granted_by=None)


async def test_revoke_tool_permission_removes_a_real_row(db_session):
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    await grant_tool_permission(db_session, org_id, "agent-1", user_id, "calculator", "deny", granted_by=None)
    await db_session.commit()

    revoked = await revoke_tool_permission(db_session, org_id, "agent-1", user_id, "calculator")
    await db_session.commit()

    assert revoked is True
    assert await check_tool_permission(db_session, org_id, "agent-1", user_id, "calculator") == "allow"


async def test_revoke_tool_permission_returns_false_for_no_match(db_session):
    assert await revoke_tool_permission(db_session, uuid.uuid4(), "agent-1", uuid.uuid4(), "calculator") is False


async def test_get_available_tools_excludes_denied_tools(db_session):
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    await grant_tool_permission(db_session, org_id, None, user_id, "calculator", "deny", granted_by=None)
    await db_session.commit()

    available = await get_available_tools(db_session, org_id, agent_id=None, user_id=user_id)
    assert CALCULATOR_TOOL not in available
    assert any(t.name == "word_count" for t in available)


# --------------------------------------- endpoints (Admin+) --


async def test_admin_can_grant_and_list_tool_permissions(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    _, target = await _register(client, db_session, "target@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), target.id, OrganizationRole.member)

    response = await client.post(
        f"/organizations/{org['id']}/agents/agent-1/tools/calculator/permissions",
        json={"user_id": str(target.id), "permission": "deny"}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    assert response.json()["permission"] == "deny"

    listing = await client.get(f"/organizations/{org['id']}/agents/agent-1/tools/permissions", headers=_auth_header(owner_token))
    assert listing.status_code == 200
    assert len(listing.json()) == 1


async def test_member_cannot_grant_tool_permissions(client, db_session, register_payload):
    """Validation criterion: sécurité -- Admin+ uniquement."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    member_token, member = await _register(client, db_session, "member@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member)

    response = await client.post(
        f"/organizations/{org['id']}/agents/agent-1/tools/calculator/permissions",
        json={"user_id": str(member.id), "permission": "deny"}, headers=_auth_header(member_token),
    )
    assert response.status_code == 403


async def test_admin_can_revoke_a_tool_permission(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    _, target = await _register(client, db_session, "target@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), target.id, OrganizationRole.member)
    await client.post(
        f"/organizations/{org['id']}/agents/agent-1/tools/calculator/permissions",
        json={"user_id": str(target.id), "permission": "deny"}, headers=_auth_header(owner_token),
    )

    response = await client.delete(
        f"/organizations/{org['id']}/agents/agent-1/tools/calculator/permissions/{target.id}", headers=_auth_header(owner_token),
    )
    assert response.status_code == 204


async def test_revoke_unknown_permission_returns_404(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.delete(
        f"/organizations/{org['id']}/agents/agent-1/tools/calculator/permissions/{uuid.uuid4()}", headers=_auth_header(owner_token),
    )
    assert response.status_code == 404


async def test_member_can_read_their_own_available_tools(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.get(f"/organizations/{org['id']}/users/me/tools/permissions", headers=_auth_header(owner_token))
    assert response.status_code == 200
    names = {t["name"] for t in response.json()}
    assert "calculator" in names

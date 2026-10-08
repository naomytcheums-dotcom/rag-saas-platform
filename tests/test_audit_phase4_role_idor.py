"""
Audit Phase 4 (RBAC) -- empirical IDOR probe for PATCH
/organizations/{org_id}/members/{user_id}/role.

Question: can the Owner of Organization A change the role of a user who
is only a member of Organization B, by passing B's user_id under A's
org_id in the URL?

Expected (per api/security/organizations.py's get_organization_member_or_404,
which filters by BOTH organization_id AND user_id) is 404 -- the target
lookup is scoped to the org_id in the path, so a user who has no
membership row in that org can't be found via it at all.
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


async def test_owner_of_org_a_cannot_change_role_of_member_only_in_org_b(client, db_session, register_payload):
    # Org A, owned by owner_a.
    owner_a_token, owner_a = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_a = await _create_org(client, owner_a_token, "Org A")

    # Org B, owned by someone else, with victim as a (say) viewer member there.
    owner_b_token, owner_b = await _register(client, db_session, "owner-b@example.com")
    org_b = await _create_org(client, owner_b_token, "Org B")

    victim_token, victim = await _register(client, db_session, "victim@example.com")
    await _add_member(db_session, uuid.UUID(org_b["id"]), victim.id, OrganizationRole.viewer, invited_by=owner_b.id)

    # Sanity: victim has NO membership row at all in org A.
    membership_in_a = await db_session.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == uuid.UUID(org_a["id"]), OrganizationMember.user_id == victim.id,
        )
    )
    assert membership_in_a is None

    # Attack: owner of Org A tries to PATCH the victim's role using Org A's
    # org_id in the path (the victim's user_id is real, just not a member
    # of org_a).
    response = await client.patch(
        f"/organizations/{org_a['id']}/members/{victim.id}/role",
        json={"role": "admin"},
        headers=_auth_header(owner_a_token),
    )
    assert response.status_code == 404, response.text

    # Confirm the victim's real membership (in org B) was untouched.
    membership_in_b = await db_session.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == uuid.UUID(org_b["id"]), OrganizationMember.user_id == victim.id,
        )
    )
    assert membership_in_b is not None
    assert membership_in_b.role == OrganizationRole.viewer


async def test_viewer_cannot_change_own_or_others_role_in_own_org(client, db_session, register_payload):
    """Second empirical check while we're here: a Viewer (no members:write)
    in their OWN org must not be able to hit the role-change endpoint at
    all, confirming require_permission("members:write") is actually
    enforced on this route and not just decorative."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    viewer_token, viewer = await _register(client, db_session, "viewer@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), viewer.id, OrganizationRole.viewer, invited_by=owner.id)

    member_token, member_user = await _register(client, db_session, "member@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member_user.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.patch(
        f"/organizations/{org['id']}/members/{member_user.id}/role",
        json={"role": "admin"},
        headers=_auth_header(viewer_token),
    )
    assert response.status_code == 403, response.text

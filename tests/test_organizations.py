"""
Etape 1.2.2 -- Organizations + the auto-created default organization at
registration. Fast SQLite suite (conftest.py's `client`/`db_session`),
same tier as tests/test_roles_and_permissions.py -- pure DB/dependency
logic, no external infrastructure needed.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from api.models.organization import Organization, OrganizationMember, OrganizationRole
from api.models.user import User


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


# -------------------------------------------- auto-created default org -

async def test_registration_creates_a_default_organization_owned_by_the_new_user(client, db_session, register_payload):
    access_token, user = await _register(client, db_session, register_payload["email"], register_payload["password"])

    membership = await db_session.scalar(
        select(OrganizationMember).where(OrganizationMember.user_id == user.id)
    )
    assert membership is not None
    assert membership.role == OrganizationRole.owner
    assert membership.invited_by is None

    organization = await db_session.get(Organization, membership.organization_id)
    assert organization is not None
    assert organization.name == f"Organisation de {register_payload['email']}"


async def test_registration_still_succeeds_and_the_org_is_visible_via_the_api(client, db_session, register_payload):
    access_token, _ = await _register(client, db_session, register_payload["email"], register_payload["password"])

    response = await client.get("/organizations", headers=_auth_header(access_token))
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["my_role"] == "owner"


# ------------------------------------------------------------ 1.2.2 ----

async def test_creating_an_organization_makes_the_creator_its_owner(client, db_session, register_payload):
    access_token, user = await _register(client, db_session, register_payload["email"], register_payload["password"])

    response = await client.post("/organizations", json={"name": "Acme Corp"}, headers=_auth_header(access_token))
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Acme Corp"
    assert body["my_role"] == "owner"
    assert body["slug"]  # non-empty, generated

    membership = await db_session.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == uuid.UUID(body["id"]), OrganizationMember.user_id == user.id,
        )
    )
    assert membership is not None
    assert membership.role == OrganizationRole.owner


async def test_a_user_sees_both_their_default_org_and_a_newly_created_one(client, db_session, register_payload):
    access_token, _ = await _register(client, db_session, register_payload["email"], register_payload["password"])
    await client.post("/organizations", json={"name": "Second Org"}, headers=_auth_header(access_token))

    response = await client.get("/organizations", headers=_auth_header(access_token))
    assert response.status_code == 200
    names = {item["name"] for item in response.json()["items"]}
    assert "Second Org" in names
    assert len(response.json()["items"]) == 2


async def test_a_member_can_view_organization_details(client, db_session, register_payload):
    access_token, _ = await _register(client, db_session, register_payload["email"], register_payload["password"])
    created = (await client.post("/organizations", json={"name": "Viewable Org"}, headers=_auth_header(access_token))).json()

    response = await client.get(f"/organizations/{created['id']}", headers=_auth_header(access_token))
    assert response.status_code == 200
    assert response.json()["name"] == "Viewable Org"


async def test_a_non_member_gets_404_for_an_organization_they_do_not_belong_to(client, db_session, register_payload):
    access_token, _ = await _register(client, db_session, register_payload["email"], register_payload["password"])
    created = (await client.post("/organizations", json={"name": "Private Org"}, headers=_auth_header(access_token))).json()

    outsider_token, _ = await _register(client, db_session, "outsider@example.com")

    response = await client.get(f"/organizations/{created['id']}", headers=_auth_header(outsider_token))
    assert response.status_code == 404


async def test_owner_can_rename_the_organization(client, db_session, register_payload):
    access_token, _ = await _register(client, db_session, register_payload["email"], register_payload["password"])
    created = (await client.post("/organizations", json={"name": "Old Name"}, headers=_auth_header(access_token))).json()

    response = await client.patch(
        f"/organizations/{created['id']}", json={"name": "New Name"}, headers=_auth_header(access_token),
    )
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"


async def test_a_non_owner_member_cannot_rename_the_organization(client, db_session, register_payload):
    access_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    created = (await client.post("/organizations", json={"name": "Guarded Org"}, headers=_auth_header(access_token))).json()

    member_token, member_user = await _register(client, db_session, "member@example.com")
    db_session.add(OrganizationMember(
        organization_id=uuid.UUID(created["id"]), user_id=member_user.id, role=OrganizationRole.member,
    ))
    await db_session.commit()

    response = await client.patch(
        f"/organizations/{created['id']}", json={"name": "Hijacked Name"}, headers=_auth_header(member_token),
    )
    assert response.status_code == 403

    unchanged = await db_session.get(Organization, uuid.UUID(created["id"]))
    assert unchanged.name == "Guarded Org"


async def test_a_non_member_gets_404_not_403_trying_to_rename(client, db_session, register_payload):
    """require_org_member (the base layer under require_org_owner) 404s
    a non-member before role-checking even happens -- an outsider must
    not learn "this org exists but you're the wrong role" vs "this org
    doesn't exist" (same anti-enumeration shape as sessions/audit)."""
    access_token, _ = await _register(client, db_session, register_payload["email"], register_payload["password"])
    created = (await client.post("/organizations", json={"name": "Hidden Org"}, headers=_auth_header(access_token))).json()

    outsider_token, _ = await _register(client, db_session, "outsider2@example.com")
    response = await client.patch(
        f"/organizations/{created['id']}", json={"name": "Nope"}, headers=_auth_header(outsider_token),
    )
    assert response.status_code == 404


async def test_owner_can_delete_the_organization(client, db_session, register_payload):
    access_token, _ = await _register(client, db_session, register_payload["email"], register_payload["password"])
    created = (await client.post("/organizations", json={"name": "Doomed Org"}, headers=_auth_header(access_token))).json()

    response = await client.delete(f"/organizations/{created['id']}", headers=_auth_header(access_token))
    assert response.status_code == 200

    assert await db_session.get(Organization, uuid.UUID(created["id"])) is None


async def test_a_non_owner_member_cannot_delete_the_organization(client, db_session, register_payload):
    access_token, _ = await _register(client, db_session, register_payload["email"], register_payload["password"])
    created = (await client.post("/organizations", json={"name": "Protected Org"}, headers=_auth_header(access_token))).json()

    admin_token, admin_user = await _register(client, db_session, "org-admin@example.com")
    db_session.add(OrganizationMember(
        organization_id=uuid.UUID(created["id"]), user_id=admin_user.id, role=OrganizationRole.admin,
    ))
    await db_session.commit()

    response = await client.delete(f"/organizations/{created['id']}", headers=_auth_header(admin_token))
    assert response.status_code == 403

    assert await db_session.get(Organization, uuid.UUID(created["id"])) is not None


# Deleting an organization cascading to its memberships depends on the
# database's own ON DELETE CASCADE (delete_organization uses a Core
# bulk DELETE, not session.delete(), so no ORM-level cascade applies) --
# SQLite does not enforce foreign keys by default, so that behavior
# can't be verified against the fast SQLite suite here. Covered instead
# by tests/test_postgres_integration.py's
# test_deleting_an_organization_cascades_to_its_memberships, against
# real Postgres, same split that file's own docstring already documents
# for every other Postgres-specific-behavior test in this codebase.


async def test_organization_creation_is_recorded_in_the_audit_log(client, db_session, register_payload):
    from api.models.audit_log import AuditAction, AuditLog

    access_token, user = await _register(client, db_session, register_payload["email"], register_payload["password"])
    await client.post("/organizations", json={"name": "Audited Org"}, headers=_auth_header(access_token))

    rows = (await db_session.scalars(
        select(AuditLog).where(AuditLog.action == AuditAction.ORGANIZATION_CREATED.value, AuditLog.user_id == user.id)
    )).all()
    # One for the auto-created default org at registration, one for this explicit call.
    assert len(rows) == 2


# ------------------------------------------------- User <-> Org relations

async def test_user_organizations_and_owned_organizations_properties_work(client, db_session, register_payload):
    """The relations the spec asked for on the model itself -- exercised
    with an explicit eager load, matching how this codebase always
    touches ORM relationships from async code (see User.organization_memberships's
    own docstring: never an implicit lazy-load)."""
    access_token, user = await _register(client, db_session, register_payload["email"], register_payload["password"])
    await client.post("/organizations", json={"name": "Owned Org"}, headers=_auth_header(access_token))

    other_token, other_user = await _register(client, db_session, "other-owner@example.com")
    other_org_response = await client.post("/organizations", json={"name": "Someone Else's Org"}, headers=_auth_header(other_token))
    other_org_id = uuid.UUID(other_org_response.json()["id"])
    db_session.add(OrganizationMember(organization_id=other_org_id, user_id=user.id, role=OrganizationRole.viewer))
    await db_session.commit()

    loaded_user = await db_session.scalar(
        select(User)
        .where(User.id == user.id)
        .options(selectinload(User.organization_memberships).selectinload(OrganizationMember.organization))
    )

    org_names = {org.name for org in loaded_user.organizations}
    assert org_names == {f"Organisation de {register_payload['email']}", "Owned Org", "Someone Else's Org"}

    owned_names = {org.name for org in loaded_user.owned_organizations}
    assert owned_names == {f"Organisation de {register_payload['email']}", "Owned Org"}
    assert "Someone Else's Org" not in owned_names  # viewer there, not owner

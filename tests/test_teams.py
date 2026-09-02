"""
Partie 1.3.3 -- Teams. Fast SQLite suite, same tier as
tests/test_workspaces.py and tests/test_organization_members.py.
"""

import uuid

from sqlalchemy import select

from api.models.organization import OrganizationMember, OrganizationRole
from api.models.team import Team, TeamMember, TeamRole
from api.models.user import User
from api.security.teams import check_user_in_team


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


async def _create_team(client, org_id, access_token: str, name: str = "Support") -> dict:
    return (await client.post(f"/organizations/{org_id}/teams", json={"name": name}, headers=_auth_header(access_token))).json()


# --------------------------------------------------------------- create --

async def test_manager_can_create_a_team(client, db_session, register_payload):
    """Validation criterion: a Manager can create a team."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    manager_token, manager = await _register(client, db_session, "teammanager@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), manager.id, OrganizationRole.manager, invited_by=owner.id)

    response = await client.post(
        f"/organizations/{org['id']}/teams", json={"name": "Support", "description": "Customer support"},
        headers=_auth_header(manager_token),
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Support"

    membership = await db_session.scalar(
        select(TeamMember).where(TeamMember.team_id == uuid.UUID(response.json()["id"]), TeamMember.user_id == manager.id)
    )
    assert membership is not None
    assert membership.role == TeamRole.admin  # creator becomes the team's own admin


async def test_member_cannot_create_a_team(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    member_token, member = await _register(client, db_session, "plainmember@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.post(
        f"/organizations/{org['id']}/teams", json={"name": "Nope"}, headers=_auth_header(member_token),
    )
    assert response.status_code == 403


# ---------------------------------------------------------------- list --

async def test_manager_can_list_org_teams(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await _create_team(client, org["id"], owner_token)

    manager_token, manager = await _register(client, db_session, "listmanager@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), manager.id, OrganizationRole.manager, invited_by=owner.id)

    response = await client.get(f"/organizations/{org['id']}/teams", headers=_auth_header(manager_token))
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1


async def test_member_cannot_list_org_teams(client, db_session, register_payload):
    """Unlike workspace listing (opened to all members), the spec
    explicitly scopes team listing to Manager+."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    member_token, member = await _register(client, db_session, "listmember@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.get(f"/organizations/{org['id']}/teams", headers=_auth_header(member_token))
    assert response.status_code == 403


# -------------------------------------------------------- team details --

async def test_a_team_member_can_view_the_team(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    team = await _create_team(client, org["id"], owner_token)

    member_token, member = await _register(client, db_session, "teammember1@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member, invited_by=owner.id)
    db_session.add(TeamMember(team_id=uuid.UUID(team["id"]), user_id=member.id, role=TeamRole.member))
    await db_session.commit()

    response = await client.get(f"/teams/{team['id']}", headers=_auth_header(member_token))
    assert response.status_code == 200
    assert response.json()["name"] == "Support"


async def test_a_non_team_member_cannot_view_the_team(client, db_session, register_payload):
    """Validation criterion: a non-member cannot see a team -- 404, not
    403 (anti-enumeration, same as every other org-scoped resource)."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    team = await _create_team(client, org["id"], owner_token)

    outsider_member_token, outsider_member = await _register(client, db_session, "notonteam@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), outsider_member.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.get(f"/teams/{team['id']}", headers=_auth_header(outsider_member_token))
    assert response.status_code == 404


async def test_a_non_org_member_gets_404_for_a_team(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    team = await _create_team(client, org["id"], owner_token)

    outsider_token, _ = await _register(client, db_session, "totaloutsider@example.com")

    response = await client.get(f"/teams/{team['id']}", headers=_auth_header(outsider_token))
    assert response.status_code == 404


async def test_org_manager_can_view_a_team_without_being_a_member_of_it(client, db_session, register_payload):
    """The administrative override: org Owner/Admin/Manager can always
    reach any team in their org, even without a team_members row."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    manager_token, manager = await _register(client, db_session, "overridemanager@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), manager.id, OrganizationRole.manager, invited_by=owner.id)

    team_creator_token, team_creator = await _register(client, db_session, "otherteamcreator@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), team_creator.id, OrganizationRole.manager, invited_by=owner.id)
    team = await _create_team(client, org["id"], team_creator_token, "Engineering")

    response = await client.get(f"/teams/{team['id']}", headers=_auth_header(manager_token))
    assert response.status_code == 200


# -------------------------------------------------------- rename/delete --

async def test_manager_can_rename_a_team(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    team = await _create_team(client, org["id"], owner_token, "Old Name")

    response = await client.patch(
        f"/teams/{team['id']}", json={"name": "New Name"}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"


async def test_team_admin_who_is_a_plain_org_member_cannot_rename_the_team(client, db_session, register_payload):
    """A team's own admin role manages membership, not the team's
    existence -- renaming/deleting stays org Manager+."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    team = await _create_team(client, org["id"], owner_token)

    member_token, member = await _register(client, db_session, "teamadminmember@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member, invited_by=owner.id)
    db_session.add(TeamMember(team_id=uuid.UUID(team["id"]), user_id=member.id, role=TeamRole.admin))
    await db_session.commit()

    response = await client.patch(
        f"/teams/{team['id']}", json={"name": "Hijacked"}, headers=_auth_header(member_token),
    )
    assert response.status_code == 403


async def test_manager_can_delete_a_team(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    team = await _create_team(client, org["id"], owner_token)

    response = await client.delete(f"/teams/{team['id']}", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert await db_session.get(Team, uuid.UUID(team["id"])) is None


# --------------------------------------------------------- add members --

async def test_team_admin_can_add_a_member(client, db_session, register_payload):
    """Validation criterion: a Member can be added to a team, by a team admin."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    team = await _create_team(client, org["id"], owner_token)

    _, target = await _register(client, db_session, "newteammate@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), target.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.post(
        f"/teams/{team['id']}/members", json={"email": "newteammate@example.com"}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 201
    assert response.json()["role"] == "member"

    assert await check_user_in_team(db_session, user_id=target.id, team_id=uuid.UUID(team["id"]))


async def test_team_admin_who_is_a_plain_org_member_can_manage_team_membership(client, db_session, register_payload):
    """The team's own admin role IS enough for membership management --
    it doesn't require org Manager+."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    team = await _create_team(client, org["id"], owner_token)

    team_admin_token, team_admin = await _register(client, db_session, "realteamadmin@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), team_admin.id, OrganizationRole.member, invited_by=owner.id)
    db_session.add(TeamMember(team_id=uuid.UUID(team["id"]), user_id=team_admin.id, role=TeamRole.admin))
    await db_session.commit()

    _, target = await _register(client, db_session, "addedbyteamadmin@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), target.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.post(
        f"/teams/{team['id']}/members", json={"email": "addedbyteamadmin@example.com"},
        headers=_auth_header(team_admin_token),
    )
    assert response.status_code == 201


async def test_plain_team_member_cannot_add_members(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    team = await _create_team(client, org["id"], owner_token)

    plain_token, plain_member = await _register(client, db_session, "plainteammember@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), plain_member.id, OrganizationRole.member, invited_by=owner.id)
    db_session.add(TeamMember(team_id=uuid.UUID(team["id"]), user_id=plain_member.id, role=TeamRole.member))
    await db_session.commit()

    _, target = await _register(client, db_session, "cannotbeaddedbyplain@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), target.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.post(
        f"/teams/{team['id']}/members", json={"email": "cannotbeaddedbyplain@example.com"},
        headers=_auth_header(plain_token),
    )
    assert response.status_code == 403


async def test_cannot_add_a_non_org_member_to_a_team(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    team = await _create_team(client, org["id"], owner_token)

    await _register(client, db_session, "notinorg@example.com")

    response = await client.post(
        f"/teams/{team['id']}/members", json={"email": "notinorg@example.com"}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 400


async def test_adding_an_already_present_team_member_returns_409(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    team = await _create_team(client, org["id"], owner_token)

    response = await client.post(
        f"/teams/{team['id']}/members", json={"email": register_payload["email"]}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 409  # owner already auto-added as the team's admin at creation


# ---------------------------------------------------- role update/remove --

async def test_team_admin_can_change_a_members_role(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    team = await _create_team(client, org["id"], owner_token)

    _, target = await _register(client, db_session, "promoteteammate@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), target.id, OrganizationRole.member, invited_by=owner.id)
    db_session.add(TeamMember(team_id=uuid.UUID(team["id"]), user_id=target.id, role=TeamRole.member))
    await db_session.commit()

    response = await client.patch(
        f"/teams/{team['id']}/members/{target.id}", json={"role": "admin"}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


async def test_team_admin_can_remove_a_member(client, db_session, register_payload):
    """Validation criterion: a team admin can manage members (removal)."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    team = await _create_team(client, org["id"], owner_token)

    _, target = await _register(client, db_session, "removeteammate@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), target.id, OrganizationRole.member, invited_by=owner.id)
    db_session.add(TeamMember(team_id=uuid.UUID(team["id"]), user_id=target.id, role=TeamRole.member))
    await db_session.commit()

    response = await client.delete(f"/teams/{team['id']}/members/{target.id}", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert not await check_user_in_team(db_session, user_id=target.id, team_id=uuid.UUID(team["id"]))


async def test_removing_a_user_from_the_organization_also_removes_them_from_its_teams(client, db_session, register_payload):
    """Hygiene cleanup added alongside this step: a stale team_members
    row must not survive an org removal."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    team = await _create_team(client, org["id"], owner_token)

    _, target = await _register(client, db_session, "leavingtheorg@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), target.id, OrganizationRole.member, invited_by=owner.id)
    db_session.add(TeamMember(team_id=uuid.UUID(team["id"]), user_id=target.id, role=TeamRole.member))
    await db_session.commit()

    response = await client.delete(f"/organizations/{org['id']}/members/{target.id}", headers=_auth_header(owner_token))
    assert response.status_code == 200

    assert not await check_user_in_team(db_session, user_id=target.id, team_id=uuid.UUID(team["id"]))

"""
Partie 1.3.4 -- email-based organization invitations. Fast SQLite suite,
same tier as tests/test_organization_members.py.
"""

import uuid

from sqlalchemy import select

from api.models.invitation import Invitation
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
    db_session.add(OrganizationMember(organization_id=org_id, user_id=user_id, role=role, invited_by=invited_by))
    await db_session.commit()


def _extract_token(link: str) -> str:
    return link.split("token=")[1]


# ------------------------------------------------------------- create --

async def test_manager_can_invite_an_existing_user(monkeypatch, client, db_session, register_payload):
    captured = {}
    monkeypatch.setattr("api.routers.invitations.send_organization_invitation_email", lambda *a: captured.update(link=a[3]))

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    manager_token, manager = await _register(client, db_session, "invitemanager@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), manager.id, OrganizationRole.manager, invited_by=owner.id)

    _, target = await _register(client, db_session, "invitedexisting@example.com")

    response = await client.post(
        f"/organizations/{org['id']}/invitations", json={"email": "invitedexisting@example.com", "role": "member"},
        headers=_auth_header(manager_token),
    )
    assert response.status_code == 201
    assert response.json()["email"] == "invitedexisting@example.com"
    assert "link" in captured


async def test_manager_can_invite_a_new_user(monkeypatch, client, db_session, register_payload):
    monkeypatch.setattr("api.routers.invitations.send_organization_invitation_email", lambda *a: None)

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(
        f"/organizations/{org['id']}/invitations", json={"email": "brandnew@example.com", "role": "member"},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 201

    invitation = await db_session.scalar(select(Invitation).where(Invitation.email == "brandnew@example.com"))
    assert invitation is not None
    assert invitation.accepted_at is None


async def test_manager_cannot_invite_an_existing_member(monkeypatch, client, db_session, register_payload):
    """Validation criterion: a Manager cannot invite someone already a member."""
    monkeypatch.setattr("api.routers.invitations.send_organization_invitation_email", lambda *a: None)

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    _, existing_member = await _register(client, db_session, "alreadythere@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), existing_member.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.post(
        f"/organizations/{org['id']}/invitations", json={"email": "alreadythere@example.com", "role": "member"},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 409


async def test_non_manager_cannot_create_an_invitation(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    member_token, member = await _register(client, db_session, "plainmember@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), member.id, OrganizationRole.member, invited_by=owner.id)

    response = await client.post(
        f"/organizations/{org['id']}/invitations", json={"email": "someone@example.com", "role": "member"},
        headers=_auth_header(member_token),
    )
    assert response.status_code == 403


async def test_manager_cannot_invite_as_admin(monkeypatch, client, db_session, register_payload):
    """Carries over Etape 1.2.4's privilege-escalation guard: a Manager
    can't invite someone in as admin/manager."""
    monkeypatch.setattr("api.routers.invitations.send_organization_invitation_email", lambda *a: None)

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    manager_token, manager = await _register(client, db_session, "escalatingmanager@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), manager.id, OrganizationRole.manager, invited_by=owner.id)

    response = await client.post(
        f"/organizations/{org['id']}/invitations", json={"email": "wouldbeadmin@example.com", "role": "admin"},
        headers=_auth_header(manager_token),
    )
    assert response.status_code == 403


async def test_cannot_invite_someone_as_owner(client, db_session, register_payload):
    owner_token, _ = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(
        f"/organizations/{org['id']}/invitations", json={"email": "wouldbeowner@example.com", "role": "owner"},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 422


async def test_reinviting_the_same_email_reissues_the_same_row(monkeypatch, client, db_session, register_payload):
    monkeypatch.setattr("api.routers.invitations.send_organization_invitation_email", lambda *a: None)

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    first = await client.post(
        f"/organizations/{org['id']}/invitations", json={"email": "reinvite@example.com", "role": "member"},
        headers=_auth_header(owner_token),
    )
    second = await client.post(
        f"/organizations/{org['id']}/invitations", json={"email": "reinvite@example.com", "role": "manager"},
        headers=_auth_header(owner_token),
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["role"] == "manager"

    rows = (await db_session.scalars(select(Invitation).where(Invitation.email == "reinvite@example.com"))).all()
    assert len(rows) == 1


# --------------------------------------------------------------- list --

async def test_manager_can_list_invitations(monkeypatch, client, db_session, register_payload):
    monkeypatch.setattr("api.routers.invitations.send_organization_invitation_email", lambda *a: None)

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.post(
        f"/organizations/{org['id']}/invitations", json={"email": "listed@example.com", "role": "member"},
        headers=_auth_header(owner_token),
    )

    response = await client.get(f"/organizations/{org['id']}/invitations", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1


# ------------------------------------------------------------- cancel --

async def test_manager_can_cancel_an_invitation(monkeypatch, client, db_session, register_payload):
    monkeypatch.setattr("api.routers.invitations.send_organization_invitation_email", lambda *a: None)

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = (await client.post(
        f"/organizations/{org['id']}/invitations", json={"email": "cancelme@example.com", "role": "member"},
        headers=_auth_header(owner_token),
    )).json()

    response = await client.delete(f"/organizations/{org['id']}/invitations/{created['id']}", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert await db_session.get(Invitation, uuid.UUID(created["id"])) is None


async def test_cancelling_a_nonexistent_invitation_returns_404(client, db_session, register_payload):
    owner_token, _ = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.delete(f"/organizations/{org['id']}/invitations/{uuid.uuid4()}", headers=_auth_header(owner_token))
    assert response.status_code == 404


# ------------------------------------------------------------- accept --

async def test_accepting_with_a_valid_token_adds_an_existing_user(monkeypatch, client, db_session, register_payload):
    """Validation criterion: acceptance with a valid token works, for an
    existing user."""
    captured = {}
    monkeypatch.setattr("api.routers.invitations.send_organization_invitation_email", lambda *a: captured.update(link=a[3]))
    monkeypatch.setattr("api.routers.invitations.send_organization_member_added_email", lambda *a: None)

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    _, target = await _register(client, db_session, "acceptexisting@example.com")
    await client.post(
        f"/organizations/{org['id']}/invitations", json={"email": "acceptexisting@example.com", "role": "manager"},
        headers=_auth_header(owner_token),
    )

    response = await client.post("/invitations/accept", json={"token": _extract_token(captured["link"])})
    assert response.status_code == 200
    assert "access_token" not in response.json()  # existing user -- not auto-logged in

    membership = await db_session.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == uuid.UUID(org["id"]), OrganizationMember.user_id == target.id,
        )
    )
    assert membership is not None
    assert membership.role == OrganizationRole.manager


async def test_accepting_with_a_valid_token_creates_a_new_account(monkeypatch, client, db_session, register_payload):
    """Validation criterion: a new user can be created via acceptance."""
    captured = {}
    monkeypatch.setattr("api.routers.invitations.send_organization_invitation_email", lambda *a: captured.update(link=a[3]))
    monkeypatch.setattr("api.services.verification.send_verification_code_email", lambda *a: None)

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    await client.post(
        f"/organizations/{org['id']}/invitations", json={"email": "brandnewaccount@example.com", "role": "member"},
        headers=_auth_header(owner_token),
    )

    response = await client.post("/invitations/accept", json={
        "token": _extract_token(captured["link"]), "password": "a-brand-new-password-123",
        "full_name": "Brand New", "accept_terms": True,
    })
    assert response.status_code == 200
    assert "access_token" in response.json()

    new_user = await db_session.scalar(select(User).where(User.email == "brandnewaccount@example.com"))
    assert new_user is not None
    membership = await db_session.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == uuid.UUID(org["id"]), OrganizationMember.user_id == new_user.id,
        )
    )
    assert membership is not None
    assert membership.role == OrganizationRole.member

    # No auto-created default organization for this path -- see
    # api/routers/invitations.py's accept_invitation docstring.
    owned_orgs = (await db_session.scalars(
        select(OrganizationMember).where(
            OrganizationMember.user_id == new_user.id, OrganizationMember.role == OrganizationRole.owner,
        )
    )).all()
    assert owned_orgs == []


async def test_accepting_a_new_account_without_password_fails(monkeypatch, client, db_session, register_payload):
    captured = {}
    monkeypatch.setattr("api.routers.invitations.send_organization_invitation_email", lambda *a: captured.update(link=a[3]))

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.post(
        f"/organizations/{org['id']}/invitations", json={"email": "nopassword@example.com", "role": "member"},
        headers=_auth_header(owner_token),
    )

    response = await client.post("/invitations/accept", json={"token": _extract_token(captured["link"]), "accept_terms": True})
    assert response.status_code == 400


async def test_accepting_with_an_invalid_token_fails(client, db_session, register_payload):
    """Validation criterion: acceptance with an invalid token fails."""
    response = await client.post("/invitations/accept", json={"token": "not-a-real-token"})
    assert response.status_code == 400


async def test_accepting_an_already_accepted_invitation_fails(monkeypatch, client, db_session, register_payload):
    """'Acceptée par une autre personne' -- a used token must not work twice."""
    captured = {}
    monkeypatch.setattr("api.routers.invitations.send_organization_invitation_email", lambda *a: captured.update(link=a[3]))
    monkeypatch.setattr("api.routers.invitations.send_organization_member_added_email", lambda *a: None)

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await _register(client, db_session, "usedonce@example.com")
    await client.post(
        f"/organizations/{org['id']}/invitations", json={"email": "usedonce@example.com", "role": "member"},
        headers=_auth_header(owner_token),
    )

    token = _extract_token(captured["link"])
    first = await client.post("/invitations/accept", json={"token": token})
    second = await client.post("/invitations/accept", json={"token": token})
    assert first.status_code == 200
    assert second.status_code == 400


async def test_accepting_an_expired_invitation_fails(monkeypatch, client, db_session, register_payload):
    """Validation criterion: an expired invitation is rejected."""
    import datetime as dt

    from api.security.hashing import hash_token

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    raw_token = "expired-token-for-testing"
    db_session.add(Invitation(
        organization_id=uuid.UUID(org["id"]), email="expired@example.com", role=OrganizationRole.member,
        invited_by=owner.id, token_hash=hash_token(raw_token),
        expires_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1),
    ))
    await db_session.commit()

    response = await client.post("/invitations/accept", json={"token": raw_token})
    assert response.status_code == 400

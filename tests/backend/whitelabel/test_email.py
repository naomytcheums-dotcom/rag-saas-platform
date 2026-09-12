"""Partie 19 -- POST/DELETE /organizations/{org_id}/whitelabel/email
(email_sender_name/email_sender_email -- the reply-to identity on
outbound emails, distinct from Partie 1.4.5's custom-domain SENDING)."""

from sqlalchemy import select

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


async def test_configure_email_sets_sender_name_and_address(client, db_session, register_payload):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(
        f"/organizations/{org['id']}/whitelabel/email",
        json={"sender_name": "Acme Support", "sender_email": "support@acme-reseller.example"},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email_sender_name"] == "Acme Support"
    assert body["email_sender_email"] == "support@acme-reseller.example"


async def test_configure_email_rejects_an_invalid_address(client, db_session, register_payload):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(
        f"/organizations/{org['id']}/whitelabel/email",
        json={"sender_name": "Acme Support", "sender_email": "not-an-email"},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 422


async def test_remove_email_config_clears_both_fields(client, db_session, register_payload):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.post(
        f"/organizations/{org['id']}/whitelabel/email",
        json={"sender_name": "Acme Support", "sender_email": "support@acme-reseller.example"},
        headers=_auth_header(owner_token),
    )

    response = await client.delete(f"/organizations/{org['id']}/whitelabel/email", headers=_auth_header(owner_token))
    assert response.status_code == 200
    body = response.json()
    assert body["email_sender_name"] is None
    assert body["email_sender_email"] is None


async def test_member_cannot_configure_email(client, db_session, register_payload):
    from api.models.organization import OrganizationMember, OrganizationRole
    import uuid

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    member_token, member = await _register(client, db_session, "wl_email_member@example.com")
    db_session.add(OrganizationMember(organization_id=uuid.UUID(org["id"]), user_id=member.id, role=OrganizationRole.member, invited_by=owner.id))
    await db_session.commit()

    response = await client.post(
        f"/organizations/{org['id']}/whitelabel/email",
        json={"sender_name": "x", "sender_email": "x@example.com"},
        headers=_auth_header(member_token),
    )
    assert response.status_code == 403

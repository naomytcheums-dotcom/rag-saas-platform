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


async def _verified_email_domain(db_session, org_id: str, domain: str = "acme-reseller.example"):
    """A domain of the organization whose e-mail ownership is verified (1.4.5): the only kind of domain a sender address may belong to (1.4.9)."""
    import uuid

    from api.models.custom_domain import CustomDomain

    db_session.add(CustomDomain(organization_id=uuid.UUID(org_id), domain=domain, verification_token="t" * 40, email_verified=True))
    await db_session.commit()


async def test_configure_email_sets_sender_name_and_address(client, db_session, register_payload):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await _verified_email_domain(db_session, org["id"])

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
    await _verified_email_domain(db_session, org["id"])
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


async def test_a_sender_address_outside_the_organizations_verified_domains_is_refused(client, db_session, register_payload):
    """1.4.9 -- the address is the `From` of real e-mails: no impersonation of the platform or of any domain the organization does not hold."""
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    url = f"/organizations/{org['id']}/whitelabel/email"
    for forbidden in ("ceo@bank.example", "no-reply@example.com", "support@acme-reseller.example"):  # the last: own domain but not registered/verified yet
        response = await client.post(url, json={"sender_name": "Acme", "sender_email": forbidden}, headers=_auth_header(owner_token))
        assert response.status_code == 400, forbidden
    assert (await client.get(f"/organizations/{org['id']}/whitelabel/config", headers=_auth_header(owner_token))).json()["email_sender_email"] is None
    # registered but e-mail ownership not verified: still refused
    from api.models.custom_domain import CustomDomain
    import uuid

    db_session.add(CustomDomain(organization_id=uuid.UUID(org["id"]), domain="acme-reseller.example", verification_token="t" * 40, email_verified=False))
    await db_session.commit()
    response = await client.post(url, json={"sender_name": "Acme", "sender_email": "support@acme-reseller.example"}, headers=_auth_header(owner_token))
    assert response.status_code == 400


async def test_another_organizations_verified_domain_cannot_be_used_as_sender(client, db_session, register_payload):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    other_token, _other = await _register(client, db_session, "wl_other_owner@example.com")
    other_org = await _create_org(client, other_token, "Other")
    await _verified_email_domain(db_session, other_org["id"], "other-company.example")
    response = await client.post(
        f"/organizations/{org['id']}/whitelabel/email", json={"sender_name": "Acme", "sender_email": "boss@other-company.example"}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 400


async def test_the_sender_name_cannot_pose_as_a_second_address(client, db_session, register_payload):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await _verified_email_domain(db_session, org["id"])
    for name in ("CEO <ceo@bank.example>", 'Acme "Support"', "Acme" + chr(13) + chr(10) + "Bcc: x@y.z"):
        response = await client.post(
            f"/organizations/{org['id']}/whitelabel/email", json={"sender_name": name, "sender_email": "support@acme-reseller.example"}, headers=_auth_header(owner_token),
        )
        assert response.status_code == 400, name


async def test_deleting_the_domain_clears_the_sender_identity(client, db_session, register_payload):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await _verified_email_domain(db_session, org["id"])
    ok = await client.post(
        f"/organizations/{org['id']}/whitelabel/email", json={"sender_name": "Acme", "sender_email": "support@acme-reseller.example"}, headers=_auth_header(owner_token),
    )
    assert ok.status_code == 200
    domains = (await client.get(f"/organizations/{org['id']}/domains", headers=_auth_header(owner_token))).json()["items"]
    assert (await client.delete(f"/organizations/{org['id']}/domains/{domains[0]['id']}", headers=_auth_header(owner_token))).status_code == 200
    config = (await client.get(f"/organizations/{org['id']}/whitelabel/config", headers=_auth_header(owner_token))).json()
    assert config["email_sender_email"] is None and config["email_sender_name"] is None

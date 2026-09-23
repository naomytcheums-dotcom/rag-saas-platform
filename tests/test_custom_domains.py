"""
Partie 1.4.1 -- custom domains. Fast SQLite suite, same tier as
tests/test_quotas.py. The real DNS TXT lookup
(api/security/custom_domains.py's check_domain_dns_txt_record) is
monkeypatched throughout -- no real network call belongs in the fast
suite. The real DNS resolution path is tested for real, against the
real internet, in tests/test_dns_verification_integration.py.
"""

import uuid

from sqlalchemy import select

from api.models.custom_domain import CustomDomain, CustomDomainStatus
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.security.custom_domains import activate_domain, get_org_domain


async def _dns_matches(domain: str, token: str) -> bool:
    return True


async def _dns_does_not_match(domain: str, token: str) -> bool:
    return False


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


# ----------------------------------------------------------------- adding --

async def test_owner_can_add_a_domain(client, db_session, register_payload):
    """Validation criterion: an Owner can add a domain."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(
        f"/organizations/{org['id']}/domains", json={"domain": "app.acme-corp.example"}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 201
    assert response.json()["domain"] == "app.acme-corp.example"


async def test_new_domain_defaults_to_pending_status(client, db_session, register_payload):
    """Validation criterion: default status is 'pending'."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(
        f"/organizations/{org['id']}/domains", json={"domain": "app.acme-corp.example"}, headers=_auth_header(owner_token),
    )
    assert response.json()["status"] == CustomDomainStatus.pending.value


async def test_domain_is_normalized_to_lowercase(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(
        f"/organizations/{org['id']}/domains", json={"domain": "App.Acme-Corp.EXAMPLE"}, headers=_auth_header(owner_token),
    )
    assert response.json()["domain"] == "app.acme-corp.example"


async def test_response_includes_cname_and_txt_dns_instructions(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(
        f"/organizations/{org['id']}/domains", json={"domain": "app.acme-corp.example"}, headers=_auth_header(owner_token),
    )
    body = response.json()
    records = {record["type"]: record for record in body["dns_records"]}
    assert records["CNAME"]["name"] == "app.acme-corp.example"
    assert records["TXT"]["name"] == "_rag-saas-verify.app.acme-corp.example"
    assert records["TXT"]["value"] == body["verification_token"]


# ------------------------------------------------------ 1.4.2 -- instructions --

async def test_instructions_are_returned_for_an_existing_domain(client, db_session, register_payload):
    """Validation criterion: instructions are returned for an existing
    domain -- both per-record (dns_records[*].instructions) and the
    overall walkthrough (setup_steps)."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    created = await client.post(
        f"/organizations/{org['id']}/domains", json={"domain": "app.acme-corp.example"}, headers=_auth_header(owner_token),
    )
    body = created.json()
    assert len(body["setup_steps"]) > 0
    for record in body["dns_records"]:
        assert record["instructions"]

    # And on a fresh read, not just the creation response.
    listed = await client.get(f"/organizations/{org['id']}/domains", headers=_auth_header(owner_token))
    listed_domain = listed.json()["items"][0]
    assert len(listed_domain["setup_steps"]) > 0
    assert all(record["instructions"] for record in listed_domain["dns_records"])


async def test_instructions_contain_the_correct_values(client, db_session, register_payload):
    """Validation criterion: the instructions contain the right values --
    not generic boilerplate, the ACTUAL domain/CNAME target/token this
    domain was issued."""
    from api.config import settings

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    created = await client.post(
        f"/organizations/{org['id']}/domains", json={"domain": "app.acme-corp.example"}, headers=_auth_header(owner_token),
    )
    body = created.json()
    records = {record["type"]: record for record in body["dns_records"]}

    cname_text = records["CNAME"]["instructions"]["fr"] + records["CNAME"]["instructions"]["en"]
    assert "app.acme-corp.example" in cname_text
    assert settings.CUSTOM_DOMAIN_CNAME_TARGET in cname_text

    txt_text = records["TXT"]["instructions"]["fr"] + records["TXT"]["instructions"]["en"]
    assert "_rag-saas-verify.app.acme-corp.example" in txt_text
    assert body["verification_token"] in txt_text


async def test_instructions_are_available_in_french_and_english(client, db_session, register_payload):
    """Validation criterion: instructions are available in French and
    English."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    created = await client.post(
        f"/organizations/{org['id']}/domains", json={"domain": "app.acme-corp.example"}, headers=_auth_header(owner_token),
    )
    body = created.json()

    for record in body["dns_records"]:
        assert set(record["instructions"].keys()) == {"fr", "en"}
        assert record["instructions"]["fr"].strip()
        assert record["instructions"]["en"].strip()
        assert record["instructions"]["fr"] != record["instructions"]["en"]  # genuinely two different languages, not one copied

    for step in body["setup_steps"]:
        assert set(step.keys()) == {"fr", "en"}
        assert step["fr"].strip()
        assert step["en"].strip()
        assert step["fr"] != step["en"]


async def test_admin_cannot_add_a_domain(client, db_session, register_payload):
    """Validation criterion: a non-Owner cannot add a domain."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    admin_token, admin = await _register(client, db_session, "domainadmin@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin.id, OrganizationRole.admin, invited_by=owner.id)

    response = await client.post(
        f"/organizations/{org['id']}/domains", json={"domain": "app.acme-corp.example"}, headers=_auth_header(admin_token),
    )
    assert response.status_code == 403


async def test_a_non_member_cannot_add_a_domain(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    outsider_token, outsider = await _register(client, db_session, "domainoutsider@example.com")
    response = await client.post(
        f"/organizations/{org['id']}/domains", json={"domain": "app.acme-corp.example"}, headers=_auth_header(outsider_token),
    )
    assert response.status_code == 404  # anti-enumeration


async def test_invalid_domain_format_is_rejected(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    for bad_domain in ("not a domain", "-starts-with-hyphen.example", "no-dot-at-all", "trailing-hyphen-.example"):
        response = await client.post(
            f"/organizations/{org['id']}/domains", json={"domain": bad_domain}, headers=_auth_header(owner_token),
        )
        assert response.status_code == 400, f"{bad_domain!r} should have been rejected"


async def test_cannot_register_the_platforms_own_domain(client, db_session, register_payload):
    from api.config import settings

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    response = await client.post(
        f"/organizations/{org['id']}/domains", json={"domain": settings.CUSTOM_DOMAIN_CNAME_TARGET}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 400
    assert "platform's own domain" in response.json()["detail"]


async def test_cannot_register_a_subdomain_of_the_platforms_own_root_domain(client, db_session, register_payload):
    """Phase 5, Étape 3 correctif: the pre-existing check only rejected
    an exact match against CUSTOM_DOMAIN_CNAME_TARGET -- a real
    subdomain of the platform's own root domain passed unrejected."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    for evil_domain in ("evil.rag-saas-platform.com", "rag-saas-platform.com", "sub.app.rag-saas-platform.com"):
        response = await client.post(
            f"/organizations/{org['id']}/domains", json={"domain": evil_domain}, headers=_auth_header(owner_token),
        )
        assert response.status_code == 400, evil_domain
        assert "platform's own domain" in response.json()["detail"]


async def test_cannot_register_an_already_registered_domain(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.post(f"/organizations/{org['id']}/domains", json={"domain": "app.acme-corp.example"}, headers=_auth_header(owner_token))

    other_owner_token, other_owner = await _register(client, db_session, "otherowner@example.com")
    other_org = await _create_org(client, other_owner_token, "Other Co")

    response = await client.post(
        f"/organizations/{other_org['id']}/domains", json={"domain": "app.acme-corp.example"}, headers=_auth_header(other_owner_token),
    )
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


# ---------------------------------------------------------------- listing --

async def test_owner_can_list_domains(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.post(f"/organizations/{org['id']}/domains", json={"domain": "app.acme-corp.example"}, headers=_auth_header(owner_token))
    await client.post(f"/organizations/{org['id']}/domains", json={"domain": "www.acme-corp.example"}, headers=_auth_header(owner_token))

    response = await client.get(f"/organizations/{org['id']}/domains", headers=_auth_header(owner_token))
    assert response.status_code == 200
    domains = {item["domain"] for item in response.json()["items"]}
    assert domains == {"app.acme-corp.example", "www.acme-corp.example"}


async def test_domains_from_another_organization_are_not_listed(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.post(f"/organizations/{org['id']}/domains", json={"domain": "app.acme-corp.example"}, headers=_auth_header(owner_token))

    other_owner_token, other_owner = await _register(client, db_session, "listother@example.com")
    other_org = await _create_org(client, other_owner_token, "Other Co")

    response = await client.get(f"/organizations/{other_org['id']}/domains", headers=_auth_header(other_owner_token))
    assert response.json()["items"] == []


async def test_admin_cannot_list_domains(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    admin_token, admin = await _register(client, db_session, "listadmin@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin.id, OrganizationRole.admin, invited_by=owner.id)

    response = await client.get(f"/organizations/{org['id']}/domains", headers=_auth_header(admin_token))
    assert response.status_code == 403


# -------------------------------------------------------------- deleting --

async def test_owner_can_delete_a_domain(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/domains", json={"domain": "app.acme-corp.example"}, headers=_auth_header(owner_token))
    domain_id = created.json()["id"]

    response = await client.delete(f"/organizations/{org['id']}/domains/{domain_id}", headers=_auth_header(owner_token))
    assert response.status_code == 200

    row = await db_session.scalar(select(CustomDomain).where(CustomDomain.id == uuid.UUID(domain_id)))
    assert row is None


async def test_deleting_a_domain_belonging_to_another_org_returns_404(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/domains", json={"domain": "app.acme-corp.example"}, headers=_auth_header(owner_token))
    domain_id = created.json()["id"]

    other_owner_token, other_owner = await _register(client, db_session, "deleteother@example.com")
    other_org = await _create_org(client, other_owner_token, "Other Co")

    response = await client.delete(f"/organizations/{other_org['id']}/domains/{domain_id}", headers=_auth_header(other_owner_token))
    assert response.status_code == 404

    row = await db_session.scalar(select(CustomDomain).where(CustomDomain.id == uuid.UUID(domain_id)))
    assert row is not None  # untouched


async def test_admin_cannot_delete_a_domain(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/domains", json={"domain": "app.acme-corp.example"}, headers=_auth_header(owner_token))
    domain_id = created.json()["id"]

    admin_token, admin = await _register(client, db_session, "deleteadmin@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin.id, OrganizationRole.admin, invited_by=owner.id)

    response = await client.delete(f"/organizations/{org['id']}/domains/{domain_id}", headers=_auth_header(admin_token))
    assert response.status_code == 403


# ------------------------------------------------------------ verification --

async def test_verification_succeeds_and_activates_when_dns_matches(client, db_session, register_payload, monkeypatch):
    """Validation criterion: DNS verification works, and the domain can
    be activated."""
    monkeypatch.setattr("api.security.custom_domains.check_domain_dns_txt_record", _dns_matches)

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/domains", json={"domain": "app.acme-corp.example"}, headers=_auth_header(owner_token))
    token = created.json()["verification_token"]

    response = await client.get(f"/organizations/{org['id']}/domains/verify/{token}")
    assert response.status_code == 200
    assert response.json()["status"] == CustomDomainStatus.active.value


async def test_verification_fails_gracefully_when_dns_does_not_match(client, db_session, register_payload, monkeypatch):
    """Vision critique Q3: what happens when DNS verification fails --
    a normal 200 response with status='failed', not a server error, so
    the Owner can fix their DNS and try the same link again."""
    monkeypatch.setattr("api.security.custom_domains.check_domain_dns_txt_record", _dns_does_not_match)

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/domains", json={"domain": "app.acme-corp.example"}, headers=_auth_header(owner_token))
    token = created.json()["verification_token"]

    response = await client.get(f"/organizations/{org['id']}/domains/verify/{token}")
    assert response.status_code == 200
    assert response.json()["status"] == CustomDomainStatus.failed.value


async def test_verification_can_be_retried_after_a_failure(client, db_session, register_payload, monkeypatch):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/domains", json={"domain": "app.acme-corp.example"}, headers=_auth_header(owner_token))
    token = created.json()["verification_token"]

    monkeypatch.setattr("api.security.custom_domains.check_domain_dns_txt_record", _dns_does_not_match)
    first = await client.get(f"/organizations/{org['id']}/domains/verify/{token}")
    assert first.json()["status"] == CustomDomainStatus.failed.value

    monkeypatch.setattr("api.security.custom_domains.check_domain_dns_txt_record", _dns_matches)
    second = await client.get(f"/organizations/{org['id']}/domains/verify/{token}")
    assert second.json()["status"] == CustomDomainStatus.active.value


async def test_verification_with_a_wrong_token_returns_404(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.post(f"/organizations/{org['id']}/domains", json={"domain": "app.acme-corp.example"}, headers=_auth_header(owner_token))

    response = await client.get(f"/organizations/{org['id']}/domains/verify/not-the-real-token")
    assert response.status_code == 404


async def test_verification_endpoint_requires_no_authentication(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr("api.security.custom_domains.check_domain_dns_txt_record", _dns_matches)

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/domains", json={"domain": "app.acme-corp.example"}, headers=_auth_header(owner_token))
    token = created.json()["verification_token"]

    response = await client.get(f"/organizations/{org['id']}/domains/verify/{token}")  # no Authorization header at all
    assert response.status_code == 200


# ---------------------------------------------------- security-layer logic --

async def test_activate_domain_rejects_a_domain_that_is_not_verified(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.post(f"/organizations/{org['id']}/domains", json={"domain": "app.acme-corp.example"}, headers=_auth_header(owner_token))

    try:
        await activate_domain(db_session, "app.acme-corp.example")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "must be verified" in str(exc)


async def test_get_org_domain_returns_none_when_no_domain_is_active(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    await client.post(f"/organizations/{org['id']}/domains", json={"domain": "app.acme-corp.example"}, headers=_auth_header(owner_token))

    result = await get_org_domain(db_session, uuid.UUID(org["id"]))
    assert result is None  # still pending, not active


async def test_get_org_domain_returns_the_active_domain(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr("api.security.custom_domains.check_domain_dns_txt_record", _dns_matches)

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    created = await client.post(f"/organizations/{org['id']}/domains", json={"domain": "app.acme-corp.example"}, headers=_auth_header(owner_token))
    token = created.json()["verification_token"]
    await client.get(f"/organizations/{org['id']}/domains/verify/{token}")

    result = await get_org_domain(db_session, uuid.UUID(org["id"]))
    assert result is not None
    assert result.domain == "app.acme-corp.example"

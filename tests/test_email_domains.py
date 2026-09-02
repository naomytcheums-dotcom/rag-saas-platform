"""
Partie 1.4.5 -- custom email-sending domains. Fast SQLite suite, same
tier as tests/test_custom_domains.py. Both real network dependencies
are mocked throughout: the real DNS TXT lookup
(api/security/email_domains.py's check_email_verification_txt_record /
verify_dkim's own lookup) AND Resend's real Domains API
(create_resend_domain / get_resend_domain /
trigger_resend_domain_verification) -- no real network call belongs in
the fast suite, same reasoning as tests/conftest.py's own
_stub_out_the_hibp_breach_check_by_default and
_stub_out_domain_verification_scheduling_by_default.

The real DNS resolution path AND the real Resend integration are tested
for real, against real infrastructure, in
tests/test_email_domains_integration.py.
"""

import base64
import datetime as dt
import uuid

import pytest
from cryptography.hazmat.primitives import serialization
from sqlalchemy import select

from api.config import settings
from api.models.custom_domain import CustomDomain
from api.models.organization import OrganizationMember, OrganizationRole
from api.security.email_domains import (
    generate_dkim_keys,
    get_dkim_dns_records,
    is_email_verification_expired,
    verify_dkim,
)
from api.services.email import send_via_custom_email_domain

_FAKE_RESEND_DOMAIN = {
    "id": "fake-resend-domain-id",
    "status": "not_started",
    "records": [{"record": "DKIM", "name": "resend._domainkey", "type": "TXT", "value": "p=fake", "status": "not_started"}],
}


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    from api.models.user import User

    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _create_org(client, access_token: str, name: str) -> dict:
    return (await client.post("/organizations", json={"name": name}, headers=_auth_header(access_token))).json()


async def _add_member(db_session, org_id, user_id, role: OrganizationRole, invited_by=None):
    db_session.add(OrganizationMember(organization_id=org_id, user_id=user_id, role=role, invited_by=invited_by))
    await db_session.commit()


async def _add_domain(client, db_session, owner_token: str, org_id: str, domain: str) -> tuple[str, CustomDomain]:
    created = await client.post(f"/organizations/{org_id}/domains", json={"domain": domain}, headers=_auth_header(owner_token))
    domain_id = created.json()["id"]
    row = await db_session.scalar(select(CustomDomain).where(CustomDomain.id == uuid.UUID(domain_id)))
    return domain_id, row


@pytest.fixture(autouse=True)
def _stub_resend_for_this_file(monkeypatch):
    """Every test in this file that reaches ensure_email_domain_setup
    would otherwise make a REAL call to Resend's Domains API (a real
    RESEND_API_KEY is configured in this project's own .env for the
    password-reset/etc. emails api/services/email.py already sends for
    real) -- scoped to this file only (not tests/conftest.py) since no
    other test file's code path reaches api/security/email_domains.py
    at all."""
    monkeypatch.setattr("api.security.email_domains.create_resend_domain", lambda domain: dict(_FAKE_RESEND_DOMAIN))
    monkeypatch.setattr("api.security.email_domains.get_resend_domain", lambda resend_domain_id: dict(_FAKE_RESEND_DOMAIN))
    monkeypatch.setattr("api.security.email_domains.trigger_resend_domain_verification", lambda resend_domain_id: {"object": "domain", "id": resend_domain_id})


async def _dns_matches(domain: str, token: str) -> bool:
    return True


async def _dns_does_not_match(domain: str, token: str) -> bool:
    return False


# ------------------------------------------------------------ generate_dkim_keys --

def test_generate_dkim_keys_returns_a_valid_rsa_2048_keypair():
    private_pem, public_b64 = generate_dkim_keys()

    private_key = serialization.load_pem_private_key(private_pem.encode(), password=None)
    assert private_key.key_size == 2048

    public_der = base64.b64decode(public_b64)
    public_key = serialization.load_der_public_key(public_der)
    assert public_key.key_size == 2048
    # The public key embedded in the private key must be the SAME one
    # returned separately -- not two unrelated freshly-generated keys.
    matching_public_der = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.DER, format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    assert matching_public_der == public_der


def test_generate_dkim_keys_returns_a_fresh_keypair_every_call():
    (private_a, public_a), (private_b, public_b) = generate_dkim_keys(), generate_dkim_keys()
    assert private_a != private_b
    assert public_a != public_b


# --------------------------------------------------------- get_dkim_dns_records --

def test_get_dkim_dns_records_returns_the_ownership_and_dkim_records():
    records = get_dkim_dns_records("app.acme-corp.example", "rag-saas", "fake-public-key-b64", "fake-token")
    by_purpose = {record["purpose"]: record for record in records}

    assert by_purpose["ownership"]["type"] == "TXT"
    assert by_purpose["ownership"]["name"] == "_rag-verify.app.acme-corp.example"
    assert by_purpose["ownership"]["value"] == "fake-token"

    assert by_purpose["dkim"]["type"] == "TXT"
    assert by_purpose["dkim"]["name"] == "rag-saas._domainkey.app.acme-corp.example"
    assert by_purpose["dkim"]["value"] == "v=DKIM1; k=rsa; p=fake-public-key-b64"


# ------------------------------------------------------------------ verify_dkim --

async def test_verify_dkim_returns_false_when_no_keys_have_been_generated_yet(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    _, row = await _add_domain(client, db_session, owner_token, org["id"], "dkim-not-set-up.acme.example")

    assert await verify_dkim(row) is False


async def test_verify_dkim_returns_true_when_dns_matches_our_own_key(client, db_session, register_payload, monkeypatch):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain_id, row = await _add_domain(client, db_session, owner_token, org["id"], "dkim-match.acme.example")

    await client.get(f"/organizations/{org['id']}/domains/{domain_id}/email/dns", headers=_auth_header(owner_token))
    await db_session.refresh(row)

    async def _dns_has_our_key(hostname: str) -> list[str]:
        return [f"v=DKIM1; k=rsa; p={row.dkim_public_key}"]

    monkeypatch.setattr("api.security.email_domains._lookup_txt_records", _dns_has_our_key)
    assert await verify_dkim(row) is True


async def test_verify_dkim_returns_false_when_dns_has_a_different_key(client, db_session, register_payload, monkeypatch):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain_id, row = await _add_domain(client, db_session, owner_token, org["id"], "dkim-mismatch.acme.example")
    await client.get(f"/organizations/{org['id']}/domains/{domain_id}/email/dns", headers=_auth_header(owner_token))
    await db_session.refresh(row)

    async def _dns_has_someone_elses_key(hostname: str) -> list[str]:
        return ["v=DKIM1; k=rsa; p=not-the-right-key"]

    monkeypatch.setattr("api.security.email_domains._lookup_txt_records", _dns_has_someone_elses_key)
    assert await verify_dkim(row) is False


# --------------------------------------------------------- is_email_verification_expired --

def test_is_not_expired_when_verification_never_started():
    row = CustomDomain(domain="never-started.example", verification_token="x", email_verification_started_at=None)
    assert is_email_verification_expired(row) is False


def test_is_expired_after_the_timeout_window_has_passed():
    row = CustomDomain(
        domain="expired.example", verification_token="x",
        email_verification_started_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=settings.EMAIL_DOMAIN_VERIFICATION_TIMEOUT_HOURS + 1),
    )
    assert is_email_verification_expired(row) is True


def test_is_not_expired_within_the_timeout_window():
    row = CustomDomain(
        domain="fresh.example", verification_token="x",
        email_verification_started_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1),
    )
    assert is_email_verification_expired(row) is False


def test_an_already_verified_domain_is_never_considered_expired():
    row = CustomDomain(
        domain="verified.example", verification_token="x", email_verified=True,
        email_verification_started_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=999),
    )
    assert is_email_verification_expired(row) is False


# ---------------------------------------------------------------- verify endpoint --

async def test_owner_can_verify_email_domain_ownership(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr("api.security.email_domains.check_email_verification_txt_record", _dns_matches)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain_id, _ = await _add_domain(client, db_session, owner_token, org["id"], "verify-match.acme.example")

    response = await client.post(f"/organizations/{org['id']}/domains/{domain_id}/email/verify", headers=_auth_header(owner_token))
    assert response.status_code == 200
    body = response.json()
    assert body["email_verified"] is True
    assert body["status"] == "verified"
    assert body["email_verification_attempts"] == 1


async def test_verification_fails_gracefully_when_dns_does_not_match(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr("api.security.email_domains.check_email_verification_txt_record", _dns_does_not_match)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain_id, _ = await _add_domain(client, db_session, owner_token, org["id"], "verify-nomatch.acme.example")

    response = await client.post(f"/organizations/{org['id']}/domains/{domain_id}/email/verify", headers=_auth_header(owner_token))
    assert response.status_code == 200
    body = response.json()
    assert body["email_verified"] is False
    assert body["status"] == "pending"
    assert body["email_verification_attempts"] == 1


async def test_verifying_an_already_verified_domain_does_not_increment_attempts(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr("api.security.email_domains.check_email_verification_txt_record", _dns_matches)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain_id, _ = await _add_domain(client, db_session, owner_token, org["id"], "verify-twice.acme.example")

    await client.post(f"/organizations/{org['id']}/domains/{domain_id}/email/verify", headers=_auth_header(owner_token))
    second = await client.post(f"/organizations/{org['id']}/domains/{domain_id}/email/verify", headers=_auth_header(owner_token))
    assert second.json()["email_verification_attempts"] == 1  # unchanged -- no-op once verified


async def test_verification_does_not_retry_past_the_timeout(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr("api.security.email_domains.check_email_verification_txt_record", _dns_matches)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain_id, row = await _add_domain(client, db_session, owner_token, org["id"], "verify-expired.acme.example")

    # First call establishes email_verification_started_at (DNS not yet
    # matching at this point) -- then we simulate the deadline having
    # already passed before the Owner ever comes back to retry.
    monkeypatch.setattr("api.security.email_domains.check_email_verification_txt_record", _dns_does_not_match)
    await client.post(f"/organizations/{org['id']}/domains/{domain_id}/email/verify", headers=_auth_header(owner_token))
    await db_session.refresh(row)
    row.email_verification_started_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=settings.EMAIL_DOMAIN_VERIFICATION_TIMEOUT_HOURS + 1)
    await db_session.commit()

    monkeypatch.setattr("api.security.email_domains.check_email_verification_txt_record", _dns_matches)
    response = await client.post(f"/organizations/{org['id']}/domains/{domain_id}/email/verify", headers=_auth_header(owner_token))
    body = response.json()
    assert body["status"] == "expired"
    assert body["email_verified"] is False
    assert body["email_verification_attempts"] == 1  # NOT incremented past the deadline


async def test_admin_cannot_verify_email_domain(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain_id, _ = await _add_domain(client, db_session, owner_token, org["id"], "verify-admin.acme.example")

    admin_token, admin = await _register(client, db_session, "emaildomainadmin@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin.id, OrganizationRole.admin, invited_by=owner.id)

    response = await client.post(f"/organizations/{org['id']}/domains/{domain_id}/email/verify", headers=_auth_header(admin_token))
    assert response.status_code == 403


async def test_verify_email_domain_for_a_domain_in_another_org_returns_404(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain_id, _ = await _add_domain(client, db_session, owner_token, org["id"], "verify-crossorg.acme.example")

    other_owner_token, other_owner = await _register(client, db_session, "emaildomaincrossorg@example.com")
    other_org = await _create_org(client, other_owner_token, "Other Co")

    response = await client.post(f"/organizations/{other_org['id']}/domains/{domain_id}/email/verify", headers=_auth_header(other_owner_token))
    assert response.status_code == 404


# ----------------------------------------------------------------- status endpoint --

async def test_status_before_any_verification_attempt(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain_id, _ = await _add_domain(client, db_session, owner_token, org["id"], "status-fresh.acme.example")

    response = await client.get(f"/organizations/{org['id']}/domains/{domain_id}/email/status", headers=_auth_header(owner_token))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "not_started"
    assert body["email_verified"] is False
    assert body["dkim_configured"] is False


async def test_status_reflects_dkim_configured_after_dns_endpoint_is_called(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain_id, _ = await _add_domain(client, db_session, owner_token, org["id"], "status-dkim.acme.example")

    await client.get(f"/organizations/{org['id']}/domains/{domain_id}/email/dns", headers=_auth_header(owner_token))
    response = await client.get(f"/organizations/{org['id']}/domains/{domain_id}/email/status", headers=_auth_header(owner_token))
    assert response.json()["dkim_configured"] is True


async def test_admin_cannot_get_email_domain_status(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain_id, _ = await _add_domain(client, db_session, owner_token, org["id"], "status-admin.acme.example")

    admin_token, admin = await _register(client, db_session, "emaildomainstatusadmin@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin.id, OrganizationRole.admin, invited_by=owner.id)

    response = await client.get(f"/organizations/{org['id']}/domains/{domain_id}/email/status", headers=_auth_header(admin_token))
    assert response.status_code == 403


# -------------------------------------------------------------------- dns endpoint --

async def test_owner_can_get_email_dns_instructions(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain_id, _ = await _add_domain(client, db_session, owner_token, org["id"], "dns-instructions.acme.example")

    response = await client.get(f"/organizations/{org['id']}/domains/{domain_id}/email/dns", headers=_auth_header(owner_token))
    assert response.status_code == 200
    body = response.json()
    purposes = {record["purpose"] for record in body["our_records"]}
    assert purposes == {"ownership", "dkim"}
    assert body["resend_domain_id"] == "fake-resend-domain-id"
    assert body["resend_records"] is not None
    assert body["resend_error"] is None


async def test_dns_endpoint_degrades_gracefully_when_resend_is_unreachable(client, db_session, register_payload, monkeypatch):
    """Vision critique Q3 -- Resend being unreachable must never turn
    into a 500; our own records are still returned."""
    monkeypatch.setattr("api.security.email_domains.create_resend_domain", lambda domain: (_ for _ in ()).throw(RuntimeError("Resend unreachable")))
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain_id, _ = await _add_domain(client, db_session, owner_token, org["id"], "dns-resend-down.acme.example")

    response = await client.get(f"/organizations/{org['id']}/domains/{domain_id}/email/dns", headers=_auth_header(owner_token))
    assert response.status_code == 200
    body = response.json()
    assert len(body["our_records"]) == 2
    assert body["resend_domain_id"] is None  # registration never succeeded
    assert body["resend_records"] is None


async def test_admin_cannot_get_email_dns_instructions(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain_id, _ = await _add_domain(client, db_session, owner_token, org["id"], "dns-admin.acme.example")

    admin_token, admin = await _register(client, db_session, "emaildomaindnsadmin@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin.id, OrganizationRole.admin, invited_by=owner.id)

    response = await client.get(f"/organizations/{org['id']}/domains/{domain_id}/email/dns", headers=_auth_header(admin_token))
    assert response.status_code == 403


# --------------------------------------------------- ensure_email_domain_setup idempotency --

async def test_calling_dns_endpoint_twice_does_not_regenerate_dkim_keys(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain_id, row = await _add_domain(client, db_session, owner_token, org["id"], "idempotent-setup.acme.example")

    await client.get(f"/organizations/{org['id']}/domains/{domain_id}/email/dns", headers=_auth_header(owner_token))
    await db_session.refresh(row)
    first_public_key = row.dkim_public_key

    await client.get(f"/organizations/{org['id']}/domains/{domain_id}/email/dns", headers=_auth_header(owner_token))
    await db_session.refresh(row)
    assert row.dkim_public_key == first_public_key


async def test_dkim_private_key_is_never_returned_by_any_endpoint(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain_id, _ = await _add_domain(client, db_session, owner_token, org["id"], "no-private-key-leak.acme.example")

    dns_response = await client.get(f"/organizations/{org['id']}/domains/{domain_id}/email/dns", headers=_auth_header(owner_token))
    status_response = await client.get(f"/organizations/{org['id']}/domains/{domain_id}/email/status", headers=_auth_header(owner_token))
    verify_response = await client.post(f"/organizations/{org['id']}/domains/{domain_id}/email/verify", headers=_auth_header(owner_token))

    for response in (dns_response, status_response, verify_response):
        assert "dkim_private_key" not in response.text
        assert "PRIVATE KEY" not in response.text


async def test_dkim_private_key_is_stored_encrypted_at_rest(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain_id, row = await _add_domain(client, db_session, owner_token, org["id"], "encrypted-at-rest.acme.example")

    await client.get(f"/organizations/{org['id']}/domains/{domain_id}/email/dns", headers=_auth_header(owner_token))
    await db_session.refresh(row)
    assert row.dkim_private_key is not None
    assert "PRIVATE KEY" not in row.dkim_private_key  # Fernet ciphertext, not the raw PEM


# --------------------------------------------------- send_via_custom_email_domain --

async def test_send_via_custom_email_domain_refuses_an_unverified_domain(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    _, row = await _add_domain(client, db_session, owner_token, org["id"], "send-unverified.acme.example")

    try:
        send_via_custom_email_domain(row, "contact", "someone@example.com", "Subject", "<p>Body</p>")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "has not completed ownership verification" in str(exc)


async def test_send_via_custom_email_domain_uses_the_custom_from_address_once_verified(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr("api.security.email_domains.check_email_verification_txt_record", _dns_matches)
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain_id, row = await _add_domain(client, db_session, owner_token, org["id"], "send-verified.acme.example")
    await client.post(f"/organizations/{org['id']}/domains/{domain_id}/email/verify", headers=_auth_header(owner_token))
    await db_session.refresh(row)

    captured = {}

    def _fake_send(to_email, subject, html_body, from_address=None):
        captured.update(to=to_email, subject=subject, html=html_body, from_address=from_address)

    monkeypatch.setattr("api.services.email._send", _fake_send)
    send_via_custom_email_domain(row, "contact", "someone@example.com", "Hello", "<p>Hi</p>")
    assert captured["from_address"] == "contact@send-verified.acme.example"
    assert captured["to"] == "someone@example.com"

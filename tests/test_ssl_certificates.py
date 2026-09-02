"""
Partie 1.4.3 -- SSL certificates. Fast SQLite suite, same tier as
tests/test_custom_domains.py. Real ACME network calls
(api/security/ssl_certificates.py's _open_order/_resume_order/
_revoke_via_acme) are monkeypatched throughout -- no real network call
belongs in the fast suite, and issuing a real certificate needs a real,
owned domain this test suite doesn't have. The real ACME protocol path
(account registration, order creation, DNS-01 challenge computation,
and honest failure detection) is verified for real, against Let's
Encrypt's staging server, in tests/test_acme_integration.py.
"""

import datetime as dt
import uuid

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from sqlalchemy import select

from api.models.custom_domain import CustomDomain, CustomDomainStatus
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.ssl_certificate import SSLCertificate, SSLCertificateStatus
from api.models.user import User
from api.security.secret_encryption import decrypt_secret


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


async def _create_active_domain(db_session, org_id, domain: str) -> dict:
    """Bypasses the real DNS-verification flow (Partie 1.4.1) -- SSL
    tests are about SSL, not re-proving domain verification, which
    already has its own dedicated test suite."""
    row = CustomDomain(organization_id=org_id, domain=domain, status=CustomDomainStatus.active.value, verification_token="irrelevant")
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return row


def _self_signed_fullchain_pem(domain: str, days_valid: int = 90) -> str:
    """A real, valid, parseable X.509 certificate (self-signed, not
    issued by any real CA) -- exercises the SAME parsing/storage code a
    genuine Let's Encrypt fullchain response would, without needing a
    real CA or a real owned domain. Two certificates concatenated (leaf
    + a second, standing in for an intermediate) so chain_pem's
    multi-cert handling is exercised too."""
    def _one_cert(common_name: str) -> str:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
        now = dt.datetime.now(dt.timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject).issuer_name(issuer).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(days=1))
            .not_valid_after(now + dt.timedelta(days=days_valid))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(domain)]), critical=False)
            .sign(key, hashes.SHA256())
        )
        return cert.public_bytes(serialization.Encoding.PEM).decode()

    return _one_cert(domain) + _one_cert("Test Intermediate CA")


# --------------------------------------------------------------- generate --

async def test_owner_can_generate_a_certificate_for_a_verified_domain(client, db_session, register_payload, monkeypatch):
    """Validation criterion: a certificate can be generated for a
    verified domain."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain = await _create_active_domain(db_session, uuid.UUID(org["id"]), "app.acme-corp.example")

    monkeypatch.setattr(
        "api.security.ssl_certificates.get_or_create_acme_account",
        lambda db: _fake_account(),
    )
    monkeypatch.setattr(
        "api.security.ssl_certificates._open_order",
        lambda account_key, account_url, domain, cert_key: (
            "https://acme.example/order/1", "https://acme.example/chall/1",
            f"_acme-challenge.{domain}", "fake-validation-value", "https://acme.example/finalize/1",
        ),
    )

    response = await client.post(
        f"/organizations/{org['id']}/domains/{domain.id}/ssl/generate", headers=_auth_header(owner_token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == SSLCertificateStatus.pending_dns01.value
    assert body["dns01_challenge"]["record_name"] == "_acme-challenge.app.acme-corp.example"
    assert body["dns01_challenge"]["record_value"] == "fake-validation-value"
    assert set(body["dns01_challenge"]["instructions"].keys()) == {"fr", "en"}


async def test_cannot_generate_a_certificate_for_an_unverified_domain(client, db_session, register_payload, monkeypatch):
    """Validation criterion: a certificate cannot be generated for an
    unverified domain."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")

    row = CustomDomain(organization_id=uuid.UUID(org["id"]), domain="pending.acme-corp.example", status=CustomDomainStatus.pending.value, verification_token="irrelevant")
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)

    monkeypatch.setattr("api.security.ssl_certificates.get_or_create_acme_account", lambda db: _fake_account())

    response = await client.post(
        f"/organizations/{org['id']}/domains/{row.id}/ssl/generate", headers=_auth_header(owner_token),
    )
    assert response.status_code == 400
    assert "must be verified" in response.json()["detail"]


async def test_missing_acme_account_email_returns_a_clear_400(client, db_session, register_payload, monkeypatch):
    from api.config import settings
    monkeypatch.setattr(settings, "ACME_ACCOUNT_EMAIL", None)

    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain = await _create_active_domain(db_session, uuid.UUID(org["id"]), "app.acme-corp.example")

    response = await client.post(
        f"/organizations/{org['id']}/domains/{domain.id}/ssl/generate", headers=_auth_header(owner_token),
    )
    assert response.status_code == 400
    assert "ACME_ACCOUNT_EMAIL" in response.json()["detail"]


async def test_admin_cannot_generate_a_certificate(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain = await _create_active_domain(db_session, uuid.UUID(org["id"]), "app.acme-corp.example")

    admin_token, admin = await _register(client, db_session, "sslgenadmin@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin.id, OrganizationRole.admin, invited_by=owner.id)

    response = await client.post(
        f"/organizations/{org['id']}/domains/{domain.id}/ssl/generate", headers=_auth_header(admin_token),
    )
    assert response.status_code == 403


async def test_generating_for_a_domain_belonging_to_another_org_returns_404(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain = await _create_active_domain(db_session, uuid.UUID(org["id"]), "app.acme-corp.example")

    other_owner_token, other_owner = await _register(client, db_session, "sslother@example.com")
    other_org = await _create_org(client, other_owner_token, "Other Co")

    response = await client.post(
        f"/organizations/{other_org['id']}/domains/{domain.id}/ssl/generate", headers=_auth_header(other_owner_token),
    )
    assert response.status_code == 404


# -------------------------------------------------------------- resuming --

async def _fake_account():
    return ("fake-account-key-placeholder", "https://acme.example/acct/1")


async def _seed_pending_certificate(db_session, org_id, domain_str: str) -> tuple[CustomDomain, SSLCertificate]:
    domain = await _create_active_domain(db_session, org_id, domain_str)
    from api.security.secret_encryption import encrypt_secret
    cert = SSLCertificate(
        domain=domain_str, status=SSLCertificateStatus.pending_dns01.value,
        key_pem_encrypted=encrypt_secret("fake-key-pem-placeholder"),
        acme_order_url="https://acme.example/order/1", acme_challenge_url="https://acme.example/chall/1",
        dns01_record_name=f"_acme-challenge.{domain_str}", dns01_record_value="fake-validation-value",
    )
    db_session.add(cert)
    await db_session.commit()
    await db_session.refresh(cert)
    return domain, cert


async def test_second_call_completes_issuance_when_dns_validates(client, db_session, register_payload, monkeypatch):
    """Validation criterion: the (real, two-phase) flow completes
    issuance -- a second call after Let's Encrypt has validated the
    challenge stores the real certificate."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain, _cert = await _seed_pending_certificate(db_session, uuid.UUID(org["id"]), "app.acme-corp.example")

    fullchain = _self_signed_fullchain_pem("app.acme-corp.example")
    monkeypatch.setattr("api.security.ssl_certificates.get_or_create_acme_account", lambda db: _fake_account())
    monkeypatch.setattr(
        "api.security.ssl_certificates._resume_order",
        lambda *a, **kw: {"outcome": "issued", "fullchain_pem": fullchain},
    )
    # cert_key isn't a real cryptography key here (it's decrypted from a
    # placeholder string) -- _resume_order is mocked out entirely, so
    # the real key is never actually used by anything in this test.
    monkeypatch.setattr("api.security.ssl_certificates._key_from_pem", lambda pem: "irrelevant-placeholder")

    response = await client.post(
        f"/organizations/{org['id']}/domains/{domain.id}/ssl/generate", headers=_auth_header(owner_token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == SSLCertificateStatus.issued.value
    assert body["cert_pem"].startswith("-----BEGIN CERTIFICATE-----")
    assert body["chain_pem"].startswith("-----BEGIN CERTIFICATE-----")
    assert body["expires_at"] is not None
    assert body["dns01_challenge"] is None
    assert "key_pem" not in body and "key_pem_encrypted" not in body


async def test_second_call_reports_failed_when_validation_fails(client, db_session, register_payload, monkeypatch):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain, _cert = await _seed_pending_certificate(db_session, uuid.UUID(org["id"]), "app.acme-corp.example")

    monkeypatch.setattr("api.security.ssl_certificates.get_or_create_acme_account", lambda db: _fake_account())
    monkeypatch.setattr(
        "api.security.ssl_certificates._resume_order",
        lambda *a, **kw: {"outcome": "failed", "detail": "simulated validation failure"},
    )
    monkeypatch.setattr("api.security.ssl_certificates._key_from_pem", lambda pem: "irrelevant-placeholder")

    response = await client.post(
        f"/organizations/{org['id']}/domains/{domain.id}/ssl/generate", headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    assert response.json()["status"] == SSLCertificateStatus.failed.value


async def test_still_pending_leaves_the_row_untouched_and_is_safe_to_retry(client, db_session, register_payload, monkeypatch):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain, cert = await _seed_pending_certificate(db_session, uuid.UUID(org["id"]), "app.acme-corp.example")

    monkeypatch.setattr("api.security.ssl_certificates.get_or_create_acme_account", lambda db: _fake_account())
    monkeypatch.setattr(
        "api.security.ssl_certificates._resume_order",
        lambda *a, **kw: {"outcome": "pending", "detail": "still propagating"},
    )
    monkeypatch.setattr("api.security.ssl_certificates._key_from_pem", lambda pem: "irrelevant-placeholder")

    response = await client.post(
        f"/organizations/{org['id']}/domains/{domain.id}/ssl/generate", headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == SSLCertificateStatus.pending_dns01.value
    assert body["dns01_challenge"]["record_value"] == cert.dns01_record_value  # unchanged


async def test_calling_generate_after_failure_starts_a_fresh_order(client, db_session, register_payload, monkeypatch):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain, cert = await _seed_pending_certificate(db_session, uuid.UUID(org["id"]), "app.acme-corp.example")
    cert.status = SSLCertificateStatus.failed.value
    await db_session.commit()

    monkeypatch.setattr("api.security.ssl_certificates.get_or_create_acme_account", lambda db: _fake_account())
    monkeypatch.setattr(
        "api.security.ssl_certificates._open_order",
        lambda account_key, account_url, domain, cert_key: (
            "https://acme.example/order/2", "https://acme.example/chall/2",
            f"_acme-challenge.{domain}", "brand-new-validation-value", "https://acme.example/finalize/2",
        ),
    )

    response = await client.post(
        f"/organizations/{org['id']}/domains/{domain.id}/ssl/generate", headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == SSLCertificateStatus.pending_dns01.value
    assert body["dns01_challenge"]["record_value"] == "brand-new-validation-value"  # a NEW challenge, not the dead one


async def test_generating_twice_for_an_issued_certificate_is_rejected(client, db_session, register_payload, monkeypatch):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain, cert = await _seed_pending_certificate(db_session, uuid.UUID(org["id"]), "app.acme-corp.example")
    cert.status = SSLCertificateStatus.issued.value
    cert.cert_pem = "-----BEGIN CERTIFICATE-----\nfake\n-----END CERTIFICATE-----"
    cert.expires_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=90)
    await db_session.commit()

    monkeypatch.setattr("api.security.ssl_certificates.get_or_create_acme_account", lambda db: _fake_account())

    response = await client.post(
        f"/organizations/{org['id']}/domains/{domain.id}/ssl/generate", headers=_auth_header(owner_token),
    )
    assert response.status_code == 400
    assert "already has an issued certificate" in response.json()["detail"]


# ----------------------------------------------------------------- status --

async def test_get_certificate_status_returns_404_when_none_requested_yet(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain = await _create_active_domain(db_session, uuid.UUID(org["id"]), "app.acme-corp.example")

    response = await client.get(f"/organizations/{org['id']}/domains/{domain.id}/ssl", headers=_auth_header(owner_token))
    assert response.status_code == 404


async def test_get_certificate_status_returns_the_pending_challenge(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain, cert = await _seed_pending_certificate(db_session, uuid.UUID(org["id"]), "app.acme-corp.example")

    response = await client.get(f"/organizations/{org['id']}/domains/{domain.id}/ssl", headers=_auth_header(owner_token))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == SSLCertificateStatus.pending_dns01.value
    assert body["dns01_challenge"]["record_value"] == cert.dns01_record_value


async def test_admin_cannot_view_certificate_status(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain = await _create_active_domain(db_session, uuid.UUID(org["id"]), "app.acme-corp.example")

    admin_token, admin = await _register(client, db_session, "sslstatusadmin@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin.id, OrganizationRole.admin, invited_by=owner.id)

    response = await client.get(f"/organizations/{org['id']}/domains/{domain.id}/ssl", headers=_auth_header(admin_token))
    assert response.status_code == 403


# ----------------------------------------------------------------- renew --

async def test_renew_requires_an_existing_issued_certificate(client, db_session, register_payload):
    """Validation criterion: renewal requires an existing issued
    certificate."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain, _cert = await _seed_pending_certificate(db_session, uuid.UUID(org["id"]), "app.acme-corp.example")  # still pending, not issued

    response = await client.post(f"/organizations/{org['id']}/domains/{domain.id}/ssl/renew", headers=_auth_header(owner_token))
    assert response.status_code == 400
    assert "no issued certificate" in response.json()["detail"]


async def test_renew_starts_a_fresh_pending_order_for_an_issued_certificate(client, db_session, register_payload, monkeypatch):
    """Validation criterion: renewal works."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain, cert = await _seed_pending_certificate(db_session, uuid.UUID(org["id"]), "app.acme-corp.example")
    cert.status = SSLCertificateStatus.issued.value
    cert.cert_pem = "-----BEGIN CERTIFICATE-----\nfake\n-----END CERTIFICATE-----"
    cert.expires_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=5)  # about to expire
    await db_session.commit()

    monkeypatch.setattr("api.security.ssl_certificates.get_or_create_acme_account", lambda db: _fake_account())
    monkeypatch.setattr(
        "api.security.ssl_certificates._open_order",
        lambda account_key, account_url, domain, cert_key: (
            "https://acme.example/order/renew", "https://acme.example/chall/renew",
            f"_acme-challenge.{domain}", "renewal-validation-value", "https://acme.example/finalize/renew",
        ),
    )

    response = await client.post(f"/organizations/{org['id']}/domains/{domain.id}/ssl/renew", headers=_auth_header(owner_token))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == SSLCertificateStatus.pending_dns01.value
    assert body["cert_pem"] is None  # cleared -- not reissued yet
    assert body["dns01_challenge"]["record_value"] == "renewal-validation-value"  # a NEW challenge


async def test_admin_cannot_renew_a_certificate(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain, cert = await _seed_pending_certificate(db_session, uuid.UUID(org["id"]), "app.acme-corp.example")
    cert.status = SSLCertificateStatus.issued.value
    await db_session.commit()

    admin_token, admin = await _register(client, db_session, "sslrenewadmin@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin.id, OrganizationRole.admin, invited_by=owner.id)

    response = await client.post(f"/organizations/{org['id']}/domains/{domain.id}/ssl/renew", headers=_auth_header(admin_token))
    assert response.status_code == 403


# ---------------------------------------------------------------- revoke --

async def test_deleting_a_pending_certificate_does_not_call_acme_revoke(client, db_session, register_payload, monkeypatch):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain, cert = await _seed_pending_certificate(db_session, uuid.UUID(org["id"]), "app.acme-corp.example")

    calls = []
    monkeypatch.setattr("api.security.ssl_certificates._revoke_via_acme", lambda *a, **kw: calls.append(a))

    response = await client.delete(f"/organizations/{org['id']}/domains/{domain.id}/ssl", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert calls == []  # nothing was ever issued -- nothing to revoke with Let's Encrypt

    row = await db_session.scalar(select(SSLCertificate).where(SSLCertificate.id == cert.id))
    assert row is None


async def test_deleting_an_issued_certificate_calls_real_acme_revoke_and_deletes_the_row(client, db_session, register_payload, monkeypatch):
    """Validation criterion (implicit in item 3's revoke_certificate):
    an issued certificate is genuinely revoked with Let's Encrypt, not
    just quietly forgotten."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain, cert = await _seed_pending_certificate(db_session, uuid.UUID(org["id"]), "app.acme-corp.example")
    cert.status = SSLCertificateStatus.issued.value
    cert.cert_pem = "-----BEGIN CERTIFICATE-----\nfake\n-----END CERTIFICATE-----"
    await db_session.commit()

    calls = []
    monkeypatch.setattr("api.security.ssl_certificates.get_or_create_acme_account", lambda db: _fake_account())
    monkeypatch.setattr("api.security.ssl_certificates._revoke_via_acme", lambda account_key, account_url, cert_pem: calls.append(cert_pem))

    response = await client.delete(f"/organizations/{org['id']}/domains/{domain.id}/ssl", headers=_auth_header(owner_token))
    assert response.status_code == 200
    assert calls == ["-----BEGIN CERTIFICATE-----\nfake\n-----END CERTIFICATE-----"]

    row = await db_session.scalar(select(SSLCertificate).where(SSLCertificate.id == cert.id))
    assert row is None


async def test_admin_cannot_delete_a_certificate(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain, _cert = await _seed_pending_certificate(db_session, uuid.UUID(org["id"]), "app.acme-corp.example")

    admin_token, admin = await _register(client, db_session, "ssldeleteadmin@example.com")
    await _add_member(db_session, uuid.UUID(org["id"]), admin.id, OrganizationRole.admin, invited_by=owner.id)

    response = await client.delete(f"/organizations/{org['id']}/domains/{domain.id}/ssl", headers=_auth_header(admin_token))
    assert response.status_code == 403


# ---------------------------------------------------------------- storage --

async def test_private_key_is_stored_encrypted_not_plaintext(client, db_session, register_payload, monkeypatch):
    """Vision critique Q1: the private key must be encrypted at rest."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    domain = await _create_active_domain(db_session, uuid.UUID(org["id"]), "app.acme-corp.example")

    monkeypatch.setattr("api.security.ssl_certificates.get_or_create_acme_account", lambda db: _fake_account())
    monkeypatch.setattr(
        "api.security.ssl_certificates._open_order",
        lambda account_key, account_url, domain, cert_key: (
            "https://acme.example/order/1", "https://acme.example/chall/1",
            f"_acme-challenge.{domain}", "fake-validation-value", "https://acme.example/finalize/1",
        ),
    )

    await client.post(f"/organizations/{org['id']}/domains/{domain.id}/ssl/generate", headers=_auth_header(owner_token))

    row = await db_session.scalar(select(SSLCertificate).where(SSLCertificate.domain == "app.acme-corp.example"))
    assert "BEGIN PRIVATE KEY" not in row.key_pem_encrypted  # not stored raw
    decrypted = decrypt_secret(row.key_pem_encrypted)
    assert "BEGIN PRIVATE KEY" in decrypted  # but genuinely recoverable with the right key

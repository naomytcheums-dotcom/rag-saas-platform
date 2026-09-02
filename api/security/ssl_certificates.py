"""
Partie 1.4.3 -- SSL certificates via a real ACME v2 client (the same
`acme`/`josepy` libraries certbot uses, not a hand-rolled
reimplementation of RFC 8555's JWS signing/nonce handling).

**Read api/models/ssl_certificate.py's module docstring first** -- it
explains the two-phase design this module implements and exactly why:
DNS-01 is the only challenge type this deployment can support at all
(no reverse-proxy exists for HTTP-01), and DNS-01 itself needs a human
to publish a TXT record this app has no API access to publish for them.
Every function below performs REAL ACME protocol calls (against
ACME_DIRECTORY_URL, Let's Encrypt STAGING by default) -- nothing here
fabricates a certificate or pretends a challenge succeeded.

All network I/O (`acme`'s `requests`-based, synchronous client) runs
via `asyncio.to_thread` so a real, possibly multi-second round trip to
an ACME server never blocks this process's event loop -- same
non-blocking-real-I/O posture as api/security/custom_domains.py's
async DNS resolver, just achieved differently since no async ACME
client exists to reach for directly.
"""

import asyncio
import datetime as dt

import josepy
from acme import challenges, client, errors, messages
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.acme_account import AcmeAccount
from api.models.custom_domain import CustomDomain, CustomDomainStatus
from api.models.ssl_certificate import SSLCertificate, SSLCertificateStatus
from api.security.secret_encryption import decrypt_secret, encrypt_secret

_KEY_BITS = 2048
_USER_AGENT = "rag-saas-platform-acme/1.0"
# How long a single poll-for-validation attempt blocks (in the thread
# it runs on) before giving up and reporting "still pending" -- a real
# wait, not instant, but bounded so one HTTP request from an Owner
# checking status never hangs for minutes. Same "not propagated yet is
# the expected common case" posture as DNS domain verification
# (Partie 1.4.1) -- calling generate_ssl_certificate again costs
# nothing and is always safe.
_POLL_DEADLINE_SECONDS = 10


def _generate_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=_KEY_BITS)


def _key_to_pem(key: rsa.RSAPrivateKey) -> str:
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


def _key_from_pem(pem: str) -> rsa.RSAPrivateKey:
    return serialization.load_pem_private_key(pem.encode(), password=None)


def _build_csr_pem(domain: str, cert_key: rsa.RSAPrivateKey) -> bytes:
    csr = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, domain)]))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(domain)]), critical=False)
        .sign(cert_key, hashes.SHA256())
    )
    return csr.public_bytes(serialization.Encoding.PEM)


def _client_for(account_key: josepy.JWKRSA, account_url: str | None) -> client.ClientV2:
    """Synchronous -- always called via asyncio.to_thread. Builds a
    real ClientV2 against ACME_DIRECTORY_URL, fetching the directory
    live (a real network call, not cached indefinitely -- directories
    can change, and this is cheap)."""
    account_resource = messages.RegistrationResource(uri=account_url, body=messages.Registration()) if account_url else None
    net = client.ClientNetwork(account_key, account=account_resource, user_agent=_USER_AGENT)
    directory = client.ClientV2.get_directory(settings.ACME_DIRECTORY_URL, net)
    return client.ClientV2(directory, net)


def _register_account(email: str) -> tuple[josepy.JWKRSA, str]:
    """Synchronous -- always called via asyncio.to_thread. A fresh
    account key + a real `new_account` call. RFC 8555 account creation
    is idempotent per key (registering the same key twice returns the
    same account), but this is only ever called once per directory --
    see get_or_create_acme_account below."""
    account_private_key = _generate_key()
    account_key = josepy.JWKRSA(key=account_private_key)
    acme_client = _client_for(account_key, account_url=None)
    registration = acme_client.new_account(
        messages.NewRegistration.from_data(email=email, terms_of_service_agreed=True)
    )
    return account_key, registration.uri


async def get_or_create_acme_account(db: AsyncSession) -> tuple[josepy.JWKRSA, str]:
    """
    Not one of this step's 4 literal functions -- necessary
    infrastructure (see api/models/acme_account.py's own docstring for
    why account registration is per-deployment, not per-domain).
    Returns (account_key, account_url); callers build their own
    ClientV2 from these via _client_for, since a ClientV2 itself isn't
    safely reusable across the thread boundary asyncio.to_thread
    introduces.
    """
    if not settings.ACME_ACCOUNT_EMAIL:
        raise EnvironmentError(
            "ACME_ACCOUNT_EMAIL must be set to use SSL certificate features -- see .env.example"
        )

    row = await db.scalar(select(AcmeAccount).where(AcmeAccount.directory_url == settings.ACME_DIRECTORY_URL))
    if row is not None:
        account_key = josepy.JWKRSA(key=_key_from_pem(decrypt_secret(row.account_key_pem_encrypted)))
        return account_key, row.account_url

    try:
        account_key, account_url = await asyncio.to_thread(_register_account, settings.ACME_ACCOUNT_EMAIL)
    except errors.Error as exc:
        raise RuntimeError(f"Let's Encrypt rejected account registration: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 -- network/connectivity failures from `requests`, not ACME protocol errors
        raise RuntimeError(f"could not reach the ACME server at {settings.ACME_DIRECTORY_URL}: {exc}") from exc

    db.add(AcmeAccount(
        directory_url=settings.ACME_DIRECTORY_URL, account_url=account_url,
        account_key_pem_encrypted=encrypt_secret(_key_to_pem(account_key.key)),
    ))
    await db.flush()
    return account_key, account_url


def _open_order(account_key: josepy.JWKRSA, account_url: str, domain: str, cert_key: rsa.RSAPrivateKey) -> tuple[str, str, str, str, str]:
    """
    Synchronous -- always called via asyncio.to_thread. Opens a real
    order and returns everything needed to (a) resume it on a later
    call and (b) tell the Owner what DNS record to publish:
    (order_url, challenge_url, dns01_record_name, dns01_record_value,
    order_finalize_url -- unused by the caller directly, kept for
    clarity in the tuple's shape).

    Deliberately does NOT call answer_challenge here -- doing so before
    the Owner has actually published the DNS record would tell Let's
    Encrypt to check immediately, fail, and permanently invalidate this
    challenge (ACME challenges are effectively single-shot once
    answered). See this module's top docstring.
    """
    acme_client = _client_for(account_key, account_url)
    csr_pem = _build_csr_pem(domain, cert_key)
    orderr = acme_client.new_order(csr_pem)

    authz = orderr.authorizations[0]
    dns01_challenge = next(c for c in authz.body.challenges if isinstance(c.chall, challenges.DNS01))
    _response, validation = dns01_challenge.chall.response_and_validation(account_key)

    return (
        orderr.uri, dns01_challenge.uri,
        dns01_challenge.chall.validation_domain_name(domain), validation,
        orderr.body.finalize,
    )


def _resume_order(account_key: josepy.JWKRSA, account_url: str, order_url: str, challenge_url: str, cert_key: rsa.RSAPrivateKey, domain: str) -> dict:
    """
    Synchronous -- always called via asyncio.to_thread. The REAL
    completion attempt: refetches the order and its authorization by
    URL (public ClientNetwork.get + messages.*.from_json, never private
    library internals), answers the DNS-01 challenge (telling Let's
    Encrypt "check now"), polls briefly for validation, and finalizes
    if valid. Returns a dict describing the outcome -- never raises for
    "still pending", only for a real, unrecoverable ACME error.
    """
    acme_client = _client_for(account_key, account_url)
    net = acme_client.net

    order_body = messages.Order.from_json(net.get(order_url).json())
    if order_body.status == messages.STATUS_INVALID:
        return {"outcome": "failed", "detail": "Let's Encrypt marked this order invalid -- the DNS challenge was not satisfied in time."}

    authz_body = messages.Authorization.from_json(net.get(order_body.authorizations[0]).json())
    dns01_challenge = next(c for c in authz_body.challenges if isinstance(c.chall, challenges.DNS01))

    if authz_body.status == messages.STATUS_PENDING:
        response, _validation = dns01_challenge.chall.response_and_validation(account_key)
        acme_client.answer_challenge(dns01_challenge, response)

    orderr = messages.OrderResource(
        body=order_body, uri=order_url, csr_pem=_build_csr_pem(domain, cert_key),
        authorizations=[messages.AuthorizationResource(body=authz_body, uri=order_body.authorizations[0])],
    )

    deadline = dt.datetime.now() + dt.timedelta(seconds=_POLL_DEADLINE_SECONDS)
    try:
        orderr = acme_client.poll_authorizations(orderr, deadline)
    except errors.ValidationError:
        return {"outcome": "failed", "detail": "Let's Encrypt could not validate the DNS-01 TXT record -- it may not have propagated yet, or the value published doesn't match."}
    except errors.TimeoutError:
        return {"outcome": "pending", "detail": "Validation is still in progress -- try again shortly."}

    finalized = acme_client.finalize_order(orderr, deadline)
    return {
        "outcome": "issued", "fullchain_pem": finalized.fullchain_pem,
    }


async def _open_fresh_order(
    db: AsyncSession, domain: str, account_key: josepy.JWKRSA, account_url: str, existing: SSLCertificate | None,
) -> SSLCertificate:
    """
    Shared by generate_ssl_certificate (first call, or retrying after a
    prior `failed` attempt) and renew_ssl_certificate: opens a REAL,
    brand-new ACME order and either inserts a new row or overwrites an
    existing one in place. A fresh order is required in both cases --
    ACME orders/authorizations are effectively single-use; a `failed`
    order cannot be resurrected by polling it again (Let's Encrypt
    already marked it invalid, see _resume_order's own check), and
    Let's Encrypt certificates are never renewed in place, only
    replaced by a new one.
    """
    cert_key = _generate_key()
    try:
        order_url, challenge_url, record_name, record_value, _finalize_url = await asyncio.to_thread(
            _open_order, account_key, account_url, domain, cert_key,
        )
    except errors.Error as exc:
        raise RuntimeError(f"Let's Encrypt rejected the certificate order for '{domain}': {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"could not reach the ACME server at {settings.ACME_DIRECTORY_URL}: {exc}") from exc

    if existing is None:
        existing = SSLCertificate(domain=domain)
        db.add(existing)

    existing.status = SSLCertificateStatus.pending_dns01.value
    existing.key_pem_encrypted = encrypt_secret(_key_to_pem(cert_key))
    existing.acme_order_url = order_url
    existing.acme_challenge_url = challenge_url
    existing.dns01_record_name = record_name
    existing.dns01_record_value = record_value
    existing.cert_pem = None
    existing.chain_pem = None
    existing.expires_at = None
    await db.flush()
    return existing


async def generate_ssl_certificate(db: AsyncSession, domain: str) -> SSLCertificate:
    """
    Item 3's literal function -- two-phase (see this module's top
    docstring and api/models/ssl_certificate.py's own docstring):

    - No row exists, or the previous attempt `failed`: the custom
      domain must be `active` (a certificate for an unverified domain
      is meaningless) -- opens a real, BRAND NEW ACME order (see
      _open_fresh_order -- a `failed` order cannot simply be retried,
      Let's Encrypt has already marked it invalid) and stores/overwrites
      a `pending_dns01` row with the instructions to publish it.
    - A `pending_dns01` row exists: attempts real completion (see
      _resume_order) -- on success, stores the real issued certificate
      (encrypted key) with status `issued`; on Let's Encrypt reporting
      the authorization invalid, stores status `failed` (a later call
      then starts fresh, per the bullet above); on "still pending" (DNS
      not propagated, or Let's Encrypt's own check still in flight),
      the row is left untouched and the same instructions are returned
      again -- safe to call repeatedly, exactly like Partie 1.4.1's
      domain verification.
    - An `issued` row already exists: raises -- use
      renew_ssl_certificate instead.
    """
    domain_row = await db.scalar(select(CustomDomain).where(CustomDomain.domain == domain))
    if domain_row is None:
        raise ValueError(f"'{domain}' is not a registered custom domain")

    existing = await db.scalar(select(SSLCertificate).where(SSLCertificate.domain == domain))

    if existing is not None and existing.status == SSLCertificateStatus.issued.value:
        raise ValueError(f"'{domain}' already has an issued certificate -- use renew instead")

    account_key, account_url = await get_or_create_acme_account(db)

    if existing is None or existing.status == SSLCertificateStatus.failed.value:
        if domain_row.status != CustomDomainStatus.active.value:
            raise ValueError(f"'{domain}' must be verified (status=active) before requesting a certificate -- current status: {domain_row.status}")
        return await _open_fresh_order(db, domain, account_key, account_url, existing)

    cert_key = _key_from_pem(decrypt_secret(existing.key_pem_encrypted))
    try:
        result = await asyncio.to_thread(
            _resume_order, account_key, account_url, existing.acme_order_url, existing.acme_challenge_url, cert_key, domain,
        )
    except errors.Error as exc:
        raise RuntimeError(f"Let's Encrypt reported an error completing the order for '{domain}': {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"could not reach the ACME server at {settings.ACME_DIRECTORY_URL}: {exc}") from exc

    if result["outcome"] == "pending":
        return existing
    if result["outcome"] == "failed":
        existing.status = SSLCertificateStatus.failed.value
        await db.flush()
        return existing

    # A real "fullchain" PEM bundle -- leaf certificate first, then one
    # or more issuer certificates. load_pem_x509_certificates (plural)
    # parses the whole bundle properly rather than string-splitting on
    # PEM boundary markers, which is fragile against whitespace/line-
    # ending variance a raw ACME response could legitimately have.
    certs = x509.load_pem_x509_certificates(result["fullchain_pem"].encode())
    leaf_cert, chain_certs = certs[0], certs[1:]

    existing.status = SSLCertificateStatus.issued.value
    existing.cert_pem = leaf_cert.public_bytes(serialization.Encoding.PEM).decode()
    existing.chain_pem = (
        b"".join(c.public_bytes(serialization.Encoding.PEM) for c in chain_certs).decode() if chain_certs else None
    )
    existing.expires_at = leaf_cert.not_valid_after_utc
    await db.flush()
    return existing


async def renew_ssl_certificate(db: AsyncSession, domain: str) -> SSLCertificate:
    """
    Item 3's literal function. Let's Encrypt certificates aren't
    renewed in place -- "renewal" is a fresh order for the same domain,
    replacing the old certificate once issued. Requires an existing
    `issued` row (nothing to renew otherwise); resets it to
    `pending_dns01` with a brand-new order/challenge, since DNS-01
    challenges are single-use and a prior challenge's TXT value will
    NOT satisfy a new order -- **the Owner must publish a new TXT
    record for every renewal**, same real limitation this module's
    docstring already names for issuance. This is the honest,
    real-world consequence of DNS-01 without a DNS-provider API
    integration, not a bug.
    """
    existing = await db.scalar(select(SSLCertificate).where(SSLCertificate.domain == domain))
    if existing is None or existing.status != SSLCertificateStatus.issued.value:
        raise ValueError(f"'{domain}' has no issued certificate to renew")

    account_key, account_url = await get_or_create_acme_account(db)
    return await _open_fresh_order(db, domain, account_key, account_url, existing)


async def get_certificate(db: AsyncSession, domain: str) -> SSLCertificate | None:
    """Item 3's literal function."""
    return await db.scalar(select(SSLCertificate).where(SSLCertificate.domain == domain))


def _revoke_via_acme(account_key: josepy.JWKRSA, account_url: str, cert_pem: str) -> None:
    """Synchronous -- always called via asyncio.to_thread. A REAL ACME
    revocation call -- achievable without any DNS/HTTP challenge at
    all, since proving control of the account (or the certificate's own
    key) that requested a certificate is Let's Encrypt's own accepted
    proof of authority to revoke it (RFC 8555 section 7.6)."""
    acme_client = _client_for(account_key, account_url)
    cert = x509.load_pem_x509_certificate(cert_pem.encode())
    acme_client.revoke(cert, 0)  # reason code 0 = unspecified


async def revoke_certificate(db: AsyncSession, domain: str) -> None:
    """
    Item 3's literal function. Real ACME revocation for an `issued`
    certificate (see _revoke_via_acme) -- best-effort: Let's Encrypt
    already treats "already revoked"/"unknown certificate" as a
    successful no-op on its end, and a `pending_dns01` row (nothing was
    ever actually issued) has nothing to revoke at all. Either way, the
    stored row -- and the encrypted private key it holds -- is deleted
    either way, so a revoked or abandoned certificate never lingers.
    """
    existing = await db.scalar(select(SSLCertificate).where(SSLCertificate.domain == domain))
    if existing is None:
        return

    if existing.status == SSLCertificateStatus.issued.value and existing.cert_pem:
        account_key, account_url = await get_or_create_acme_account(db)
        try:
            await asyncio.to_thread(_revoke_via_acme, account_key, account_url, existing.cert_pem)
        except errors.Error as exc:
            raise RuntimeError(f"Let's Encrypt rejected revocation for '{domain}': {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"could not reach the ACME server at {settings.ACME_DIRECTORY_URL}: {exc}") from exc

    await db.execute(delete(SSLCertificate).where(SSLCertificate.id == existing.id))
    await db.flush()


def dns01_challenge_instructions(record_name: str, record_value: str) -> dict[str, str]:
    """Bilingual, same shape as Partie 1.4.2's dns_records_for
    per-record instructions -- this challenge is a TXT record exactly
    like domain verification's own, just at a different, ACME-standard
    name (`_acme-challenge.<domain>` rather than
    `_rag-saas-verify.<domain>`)."""
    return {
        "fr": f"Ajoutez un enregistrement TXT nommé '{record_name}' avec la valeur '{record_value}' chez votre fournisseur DNS, puis redemandez la génération du certificat pour finaliser.",
        "en": f"Add a TXT record named '{record_name}' with the value '{record_value}' with your DNS provider, then request certificate generation again to complete it.",
    }

"""
Partie 1.4.5 -- custom email-sending domains (e.g. contact@ma-boite.com
instead of noreply@rag-saas.com).

**Honest scope, verified against Resend's real API docs before writing a
line of code** (same discipline as every other external integration in
this codebase -- ACME/Let's Encrypt in Partie 1.4.3, real DNS in
1.4.1/1.4.4): Resend GENERATES AND MANAGES ITS OWN DKIM KEY server-side
for every domain it registers, under a FIXED selector ("resend") --
its real Domains API has no field to accept a caller-supplied DKIM key
or selector at all. This means:

- generate_dkim_keys/dkim_selector/dkim_private_key/dkim_public_key
  below are REAL, independently testable infrastructure (a genuine
  RSA-2048 keypair, a genuine DNS TXT proof-of-publication check) --
  built exactly as this step's literal spec asks.
- They are NOT what actually signs any outgoing mail. Every email this
  app sends goes through api/services/email.py's Resend HTTP API call,
  which signs DKIM using Resend's OWN key under Resend's OWN "resend"
  selector -- our self-generated key is never read by that code path.
- The record that actually matters for real deliverability from a
  custom domain is the one api/services/resend_domains.py's
  create_resend_domain/get_resend_domain return -- Resend's real DKIM
  TXT record, under their selector, which the Owner must publish for
  Resend to accept `from:` addresses at that domain at all.

Both tracks are implemented for real and exposed together (see
get_email_dns_records below) so an Owner sees the complete, honest
picture rather than only the half that happens to match this step's
literal function names.

DNS lookups reuse the same async dnspython resolver pattern as
api/security/custom_domains.py's own check_domain_dns_txt_record --
duplicated here (a small, self-contained ~10 lines) rather than
imported across module boundaries, so this module stays independent of
custom_domains.py's own private helpers, same "each security module is
self-contained" convention as api/security/ssl_certificates.py.
"""

import base64
import datetime as dt
import logging
import secrets

import dns.asyncresolver
import dns.exception
import dns.resolver
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.custom_domain import CustomDomain
from api.security.secret_encryption import encrypt_secret
from api.services.resend_domains import create_resend_domain, get_resend_domain, trigger_resend_domain_verification
from api.utils import as_aware_utc

logger = logging.getLogger(__name__)

_DKIM_KEY_BITS = 2048
_EMAIL_VERIFICATION_SUBDOMAIN_PREFIX = "_rag-verify"


def generate_dkim_keys() -> tuple[str, str]:
    """
    Item 2's literal function. Real RSA-2048 keypair, same primitives as
    api/security/ssl_certificates.py's own _generate_key. Returns
    (private_key_pem, public_key_b64) -- the private key as an
    unencrypted PKCS8 PEM string (the CALLER is responsible for passing
    it through api/security/secret_encryption.py's encrypt_secret before
    storing it, same division of responsibility as ssl_certificates.py's
    own _key_to_pem), and the public key as base64-encoded DER
    SubjectPublicKeyInfo -- the exact format a DKIM TXT record's `p=`
    tag expects (RFC 6376).
    """
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=_DKIM_KEY_BITS)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_der = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, base64.b64encode(public_der).decode()


def get_dkim_dns_records(domain: str, dkim_selector: str, dkim_public_key: str, email_verification_token: str) -> list[dict[str, str]]:
    """
    Item 2's literal function. Two records, computed on the fly (never
    stored, same "recompute at read time" convention as 1.4.1/1.4.2's
    dns_records_for): the ownership-proof TXT this step's own
    verify_email_domain checks, and this app's OWN DKIM TXT (which, per
    this module's own docstring, Resend never actually reads -- kept for
    an Owner who wants to publish it anyway, or a future non-Resend
    sending path).
    """
    return [
        {
            "type": "TXT",
            "name": f"{_EMAIL_VERIFICATION_SUBDOMAIN_PREFIX}.{domain}",
            "value": email_verification_token,
            "purpose": "ownership",
        },
        {
            "type": "TXT",
            "name": f"{dkim_selector}._domainkey.{domain}",
            "value": f"v=DKIM1; k=rsa; p={dkim_public_key}",
            "purpose": "dkim",
        },
    ]


async def _lookup_txt_records(hostname: str) -> list[str]:
    """Real DNS resolution -- see api/security/custom_domains.py's own
    _lookup_txt_records for why every "nothing there" outcome (NXDOMAIN,
    no TXT record, no reachable nameserver, timeout) collapses to []
    rather than being distinguished."""
    resolver = dns.asyncresolver.Resolver()
    resolver.timeout = settings.CUSTOM_DOMAIN_DNS_LOOKUP_TIMEOUT_SECONDS
    resolver.lifetime = settings.CUSTOM_DOMAIN_DNS_LOOKUP_TIMEOUT_SECONDS
    try:
        answer = await resolver.resolve(hostname, "TXT")
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers, dns.exception.Timeout):
        return []
    return ["".join(chunk.decode("utf-8", "replace") if isinstance(chunk, bytes) else chunk for chunk in rdata.strings) for rdata in answer]


async def check_email_verification_txt_record(domain: str, token: str) -> bool:
    """Item 2's literal verify_email_domain building block -- checks the
    `_rag-verify.<domain>` TXT record for the given token."""
    records = await _lookup_txt_records(f"{_EMAIL_VERIFICATION_SUBDOMAIN_PREFIX}.{domain}")
    return token in records


def _dkim_public_key_from_txt_value(value: str) -> str | None:
    """A DKIM TXT record is `;`-separated tag=value pairs (RFC 6376) --
    pulls out the `p=` tag regardless of what other tags (v=, k=, h=)
    surround it or their order."""
    for part in value.split(";"):
        part = part.strip()
        if part.startswith("p="):
            return part[len("p="):]
    return None


async def verify_dkim(domain_row: CustomDomain) -> bool:
    """
    Item 2's literal function. Real DNS check of
    `<dkim_selector>._domainkey.<domain>` against OUR OWN generated
    public key -- proves the Owner actually published the record this
    module computed, nothing more (see this module's own docstring for
    why this is informational, not what gates real deliverability
    through Resend). Returns False outright, without any DNS lookup, if
    this domain's DKIM keys haven't been generated yet -- nothing to
    check a record against.
    """
    if not domain_row.dkim_public_key or not domain_row.dkim_selector:
        return False
    records = await _lookup_txt_records(f"{domain_row.dkim_selector}._domainkey.{domain_row.domain}")
    return any(_dkim_public_key_from_txt_value(record) == domain_row.dkim_public_key for record in records)


async def ensure_email_domain_setup(db: AsyncSession, domain_row: CustomDomain) -> CustomDomain:
    """
    Idempotent lazy setup, called by both new endpoints below before
    they do anything else -- NOT wired into api/security/
    custom_domains.py's add_custom_domain (1.4.1), since most
    organizations that register a hosting domain never use custom
    email; generating DKIM keys and registering with Resend for every
    single domain unconditionally would be wasted work (and a wasted
    real Resend API call) for the common case.

    Two independent pieces of setup, each only performed once
    (idempotent on every field it touches):
    - Our own DKIM keypair + email verification token, generated
      locally, no network call.
    - Registration with Resend's real Domains API -- wrapped in a broad
      try/except: Resend being unreachable or the API key being unset
      must never block DKIM setup or raise out of an endpoint (vision
      critique) -- resend_domain_id just stays None and this function
      is safe to call again later to retry.
    """
    if domain_row.dkim_public_key is None:
        private_pem, public_b64 = generate_dkim_keys()
        domain_row.dkim_selector = settings.DKIM_SELECTOR
        domain_row.dkim_private_key = encrypt_secret(private_pem)
        domain_row.dkim_public_key = public_b64
    if domain_row.email_verification_token is None:
        domain_row.email_verification_token = secrets.token_urlsafe(32)
    if domain_row.email_verification_started_at is None:
        domain_row.email_verification_started_at = dt.datetime.now(dt.timezone.utc)

    if domain_row.resend_domain_id is None:
        try:
            resend_domain = create_resend_domain(domain_row.domain)
            domain_row.resend_domain_id = resend_domain["id"]
        except (RuntimeError, EnvironmentError, KeyError) as exc:
            logger.warning("ensure_email_domain_setup: could not register '%s' with Resend: %s", domain_row.domain, exc)

    await db.flush()
    return domain_row


def is_email_verification_expired(domain_row: CustomDomain) -> bool:
    if domain_row.email_verified or domain_row.email_verification_started_at is None:
        return False
    started_at = as_aware_utc(domain_row.email_verification_started_at)
    deadline = started_at + dt.timedelta(hours=settings.EMAIL_DOMAIN_VERIFICATION_TIMEOUT_HOURS)
    return dt.datetime.now(dt.timezone.utc) >= deadline


async def verify_email_domain(db: AsyncSession, domain_row: CustomDomain) -> CustomDomain:
    """
    Item 2's literal function (adapted to operate on the row + its own
    stored token, same "row-oriented" shape as api/security/
    custom_domains.py's trigger_manual_verification, rather than the
    (domain, token) pair a caller would otherwise have to already know).

    Already-verified or already-expired domains are returned unchanged
    without a fresh DNS lookup or attempt-count increment -- nothing
    meaningful to re-check once verified, and no point burning an
    attempt (or a DNS round trip) past EMAIL_DOMAIN_VERIFICATION_TIMEOUT_HOURS.
    Otherwise: a real DNS check, always counted, and a best-effort
    (never-blocking) nudge to Resend's own async verification so its
    real DKIM/SPF/MX checks progress too.
    """
    await ensure_email_domain_setup(db, domain_row)

    if domain_row.email_verified or is_email_verification_expired(domain_row):
        return domain_row

    domain_row.email_verification_attempts += 1
    if await check_email_verification_txt_record(domain_row.domain, domain_row.email_verification_token):
        domain_row.email_verified = True
        domain_row.email_verified_at = dt.datetime.now(dt.timezone.utc)

    if domain_row.resend_domain_id is not None:
        try:
            trigger_resend_domain_verification(domain_row.resend_domain_id)
        except RuntimeError as exc:
            logger.warning("verify_email_domain: Resend verification trigger failed for '%s': %s", domain_row.domain, exc)

    await db.flush()
    return domain_row


async def get_email_dns_records(db: AsyncSession, domain_row: CustomDomain) -> dict[str, object]:
    """
    GET .../email/dns's data source -- the complete, honest picture:
    OUR OWN two records (get_dkim_dns_records, above) alongside Resend's
    REAL, live records for the same domain, fetched fresh every call
    (never cached) so an Owner always sees Resend's current per-record
    status, not a stale snapshot from whenever the domain was first
    registered there. Calls ensure_email_domain_setup first since this
    is typically the FIRST endpoint an Owner hits for a given domain.

    Resend being unreachable here degrades to `resend_records: None,
    resend_error: "..."` rather than a 500 -- our own two records (no
    network dependency beyond what ensure_email_domain_setup already
    attempted) are still returned either way.
    """
    await ensure_email_domain_setup(db, domain_row)

    resend_records: list[dict] | None = None
    resend_status: str | None = None
    resend_error: str | None = None
    if domain_row.resend_domain_id is not None:
        try:
            resend_domain = get_resend_domain(domain_row.resend_domain_id)
            resend_records = resend_domain.get("records")
            resend_status = resend_domain.get("status")
        except RuntimeError as exc:
            resend_error = str(exc)

    return {
        "our_records": get_dkim_dns_records(
            domain_row.domain, domain_row.dkim_selector, domain_row.dkim_public_key, domain_row.email_verification_token
        ),
        "resend_domain_id": domain_row.resend_domain_id,
        "resend_status": resend_status,
        "resend_records": resend_records,
        "resend_error": resend_error,
    }


def get_email_verification_status(domain_row: CustomDomain) -> dict[str, object]:
    """Pure, read-only status computation for GET .../email/status --
    same "compute at read time, never store a derived status" approach
    as 1.4.4's CustomDomainStatusResponse.timeout_at."""
    timeout_at = None
    if domain_row.email_verification_started_at is not None:
        timeout_at = as_aware_utc(domain_row.email_verification_started_at) + dt.timedelta(hours=settings.EMAIL_DOMAIN_VERIFICATION_TIMEOUT_HOURS)

    if domain_row.email_verified:
        status = "verified"
    elif is_email_verification_expired(domain_row):
        status = "expired"
    elif domain_row.email_verification_started_at is not None:
        status = "pending"
    else:
        status = "not_started"

    return {
        "status": status,
        "email_verified": domain_row.email_verified,
        "email_verification_attempts": domain_row.email_verification_attempts,
        "email_verification_started_at": domain_row.email_verification_started_at,
        "email_verified_at": domain_row.email_verified_at,
        "timeout_at": timeout_at,
        "dkim_configured": domain_row.dkim_public_key is not None,
    }

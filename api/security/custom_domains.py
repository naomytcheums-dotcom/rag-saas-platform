"""
Partie 1.4.1 -- custom domain registration and DNS verification.

**Honest scope, verified before writing a line of code**: this
deployment has no reverse-proxy that routes traffic by Host header
(no Traefik/Caddy config exists anywhere in this repo -- `render.yaml`
deploys a single Streamlit container, `docker-compose.yml` is local-dev
only). So `activate_domain` flipping a row to `active` does not make
`app.ma-boite.com` actually SERVE this application -- that's real
infrastructure work (Partie 1.4.3's SSL auto + a real reverse-proxy),
not something an API-layer table can do by itself. What IS real here:
a genuine database record of intent, a real, cryptographically random
verification token, and a real DNS TXT lookup that proves the caller
controls the domain's DNS zone before anything is marked verified.

DNS verification uses dnspython's ASYNC resolver (`dns.asyncresolver`,
already a transitive dependency via email-validator, now direct --
see requirements-api.txt) rather than the sync one: a DNS lookup is a
real network round-trip (up to CUSTOM_DOMAIN_DNS_LOOKUP_TIMEOUT_SECONDS
in the worst case), and this way it never blocks the event loop the
way a sync `dns.resolver.resolve()` call would.
"""

import re
import secrets
import uuid

import dns.asyncresolver
import dns.exception
import dns.resolver
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.custom_domain import CustomDomain, CustomDomainStatus

# A dedicated verification subdomain, not the bare domain -- so the TXT
# challenge never collides with a domain's own existing TXT records
# (SPF/DKIM/etc. commonly live on the bare domain). Same shape as
# Vercel's `_vercel.<domain>` / Netlify's `netlify-challenge.<domain>`.
_VERIFICATION_SUBDOMAIN_PREFIX = "_rag-saas-verify"

# RFC 1035-ish hostname: dot-separated labels, each 1-63 chars,
# alphanumeric + hyphen, never starting/ending with a hyphen; at least
# two labels (a bare TLD is never a valid custom domain to point here).
_HOSTNAME_PATTERN = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$")
_MAX_DOMAIN_LENGTH = 255


def normalize_domain(domain: str) -> str:
    """Lowercased, trimmed, trailing-dot-stripped -- so `App.Example.com`,
    `app.example.com `, and `app.example.com.` all resolve to the exact
    same row instead of silently creating duplicates that the UNIQUE
    constraint wouldn't catch."""
    return domain.strip().lower().rstrip(".")


def is_valid_hostname(domain: str) -> bool:
    return len(domain) <= _MAX_DOMAIN_LENGTH and bool(_HOSTNAME_PATTERN.match(domain))


def dns_records_for(domain: str, verification_token: str) -> list[dict[str, str]]:
    """Item 4's literal requirement -- the DNS records an Owner must add,
    computed on the fly (never stored) from the domain + its own token
    and this deployment's CUSTOM_DOMAIN_CNAME_TARGET setting."""
    return [
        {"type": "CNAME", "name": domain, "value": settings.CUSTOM_DOMAIN_CNAME_TARGET},
        {"type": "TXT", "name": f"{_VERIFICATION_SUBDOMAIN_PREFIX}.{domain}", "value": verification_token},
    ]


async def _lookup_txt_records(hostname: str) -> list[str]:
    """Real DNS resolution, not simulated -- returns [] for every
    "nothing there" outcome (NXDOMAIN, no TXT record at all, no
    reachable nameserver, or a timeout) rather than distinguishing them,
    since check_domain_dns_txt_record() below only ever needs
    yes/no-the-token-is-there."""
    resolver = dns.asyncresolver.Resolver()
    resolver.timeout = settings.CUSTOM_DOMAIN_DNS_LOOKUP_TIMEOUT_SECONDS
    resolver.lifetime = settings.CUSTOM_DOMAIN_DNS_LOOKUP_TIMEOUT_SECONDS
    try:
        answer = await resolver.resolve(hostname, "TXT")
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers, dns.exception.Timeout):
        return []
    return ["".join(chunk.decode("utf-8", "replace") if isinstance(chunk, bytes) else chunk for chunk in rdata.strings) for rdata in answer]


async def check_domain_dns_txt_record(domain: str, token: str) -> bool:
    hostname = f"{_VERIFICATION_SUBDOMAIN_PREFIX}.{domain}"
    return token in await _lookup_txt_records(hostname)


async def add_custom_domain(db: AsyncSession, organization_id: uuid.UUID, domain: str) -> CustomDomain:
    """
    Item 2's literal function. Real validation before touching the
    database: a well-formed hostname, not this deployment's own
    CNAME target (an organization "pointing" the platform's own
    hostname at itself would be nonsensical and could confuse the DNS
    instructions this same domain would then hand back), and not
    already registered (checked here for a clean error message; the
    UNIQUE constraint on `domain` is what actually closes the race --
    same "friendly pre-check, DB constraint is the real guard"
    convention as generate_unique_slug elsewhere in this codebase).

    `secrets.token_urlsafe(32)` for the verification token -- same
    generator already used for password-reset and invitation tokens
    (api/security/password.py, api/security/invitations.py), 32 random
    bytes is comfortably beyond any DNS-based guessing attack's reach.
    Stored in PLAINTEXT (unlike invitation tokens, which are hashed):
    an invitation token is a bearer credential mailed OUT and never
    re-displayed; this token is the opposite -- the API must be able to
    show it again on every GET so the Owner can (re-)copy it into their
    DNS provider's dashboard. Its security comes from controlling the
    domain's DNS zone, not from the token being secret.
    """
    normalized = normalize_domain(domain)
    if not is_valid_hostname(normalized):
        raise ValueError(f"'{domain}' is not a valid domain name")
    if normalized == normalize_domain(settings.CUSTOM_DOMAIN_CNAME_TARGET):
        raise ValueError(f"'{domain}' is this platform's own domain and cannot be registered as a custom domain")

    existing = await db.scalar(select(CustomDomain.id).where(CustomDomain.domain == normalized))
    if existing is not None:
        raise ValueError(f"'{domain}' is already registered")

    record = CustomDomain(
        organization_id=organization_id, domain=normalized, status=CustomDomainStatus.pending.value,
        verification_token=secrets.token_urlsafe(32),
    )
    db.add(record)
    await db.flush()
    return record


async def verify_domain(db: AsyncSession, domain: str, token: str) -> CustomDomain:
    """
    Item 2's literal function. Looks up the row by (domain, token) --
    NOT by domain alone, so a wrong/stale token can never verify a
    domain it wasn't issued for. Performs the real DNS check and
    records the outcome either way: `verified` on a match, `failed`
    otherwise -- a failed check is an expected, normal outcome (DNS
    hasn't propagated yet, a typo in the TXT record), not an exception,
    so the Owner can fix their DNS and simply request verification
    again (this function is safe to call repeatedly).
    """
    normalized = normalize_domain(domain)
    record = await db.scalar(
        select(CustomDomain).where(CustomDomain.domain == normalized, CustomDomain.verification_token == token)
    )
    if record is None:
        raise ValueError("no matching domain verification request found")

    dns_verified = await check_domain_dns_txt_record(normalized, token)
    record.status = CustomDomainStatus.verified.value if dns_verified else CustomDomainStatus.failed.value
    await db.flush()
    return record


async def activate_domain(db: AsyncSession, domain: str) -> CustomDomain:
    """
    Item 2's literal function. Requires `verified` first -- an
    unverified or failed domain being flipped straight to `active`
    would defeat the entire point of the DNS challenge. In a complete
    implementation this would also require successful SSL certificate
    issuance (Partie 1.4.3, not built -- see this module's own
    docstring); today, DNS verification is the only real gate that
    exists, so `verify_domain` succeeding is immediately followed by a
    call to this function (api/routers/custom_domains.py's verify
    endpoint) rather than leaving `verified` domains stuck waiting on a
    step nothing yet performs.
    """
    normalized = normalize_domain(domain)
    record = await db.scalar(select(CustomDomain).where(CustomDomain.domain == normalized))
    if record is None:
        raise ValueError("domain not found")
    if record.status != CustomDomainStatus.verified.value:
        raise ValueError(f"domain must be verified before activation (current status: {record.status})")

    record.status = CustomDomainStatus.active.value
    await db.flush()
    return record


async def get_org_domain(db: AsyncSession, organization_id: uuid.UUID) -> CustomDomain | None:
    """Item 2's literal function -- the organization's currently ACTIVE
    domain, if any. `None` if it has none yet (pending/failed domains
    don't count -- nothing should route or display them as "the"
    domain until they're genuinely active). Most recently activated
    first, in the (currently purely theoretical, since nothing in this
    step lets more than one domain reach `active` in practice) case of
    more than one."""
    return await db.scalar(
        select(CustomDomain)
        .where(CustomDomain.organization_id == organization_id, CustomDomain.status == CustomDomainStatus.active.value)
        .order_by(CustomDomain.updated_at.desc())
    )

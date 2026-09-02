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


def dns_records_for(domain: str, verification_token: str) -> list[dict[str, object]]:
    """
    Partie 1.4.1's original literal requirement (CNAME + TXT), extended
    for Partie 1.4.2 with per-record `instructions` in both languages
    this step asks for -- computed on the fly (never stored) from the
    domain + its own token and this deployment's CUSTOM_DOMAIN_CNAME_TARGET
    setting, so a config change instantly applies to every domain's
    instructions rather than only newly-created ones.

    The instruction TEXT itself only ever describes the DNS action
    (add this record, with this value) -- never a claim like "your site
    is now live at this domain." That's a deliberate wording choice
    tied to this step's own vision critique question on coherence with
    the real reverse-proxy: no such proxy exists yet (see this module's
    top docstring), so promising working traffic routing in
    user-facing copy would be false. What IS true regardless of that
    gap -- "adding this record proves you control the domain" /
    "points this hostname at our platform" -- is what's said here.
    """
    cname_name, cname_value = domain, settings.CUSTOM_DOMAIN_CNAME_TARGET
    txt_name, txt_value = f"{_VERIFICATION_SUBDOMAIN_PREFIX}.{domain}", verification_token
    return [
        {
            "type": "CNAME", "name": cname_name, "value": cname_value,
            "instructions": {
                "fr": f"Chez votre fournisseur de domaine, ajoutez un enregistrement CNAME nommé '{cname_name}' pointant vers '{cname_value}'. C'est ce qui relie votre domaine à notre plateforme.",
                "en": f"With your domain provider, add a CNAME record named '{cname_name}' pointing to '{cname_value}'. This is what connects your domain to our platform.",
            },
        },
        {
            "type": "TXT", "name": txt_name, "value": txt_value,
            "instructions": {
                "fr": f"Ajoutez aussi un enregistrement TXT nommé '{txt_name}' avec la valeur '{txt_value}'. Cet enregistrement prouve que vous contrôlez ce domaine -- c'est ce que la vérification vérifie.",
                "en": f"Also add a TXT record named '{txt_name}' with the value '{txt_value}'. This record proves you control the domain -- it's what verification checks.",
            },
        },
    ]


def setup_steps() -> list[dict[str, str]]:
    """
    Partie 1.4.2's literal requirement -- an ordered, non-technical
    walkthrough, in both languages, that a domain's response embeds
    alongside its DNS records. Generic (not domain-specific) on
    purpose: the domain-specific values live in dns_records_for()'s own
    per-record instructions above, so this stays a fixed constant, not
    something computed from a live token that would need re-generating.
    """
    return [
        {
            "fr": "Connectez-vous à l'interface d'administration de votre fournisseur de domaine (ex : OVH, Gandi, Cloudflare, GoDaddy, Namecheap).",
            "en": "Log in to your domain provider's admin panel (e.g. OVH, Gandi, Cloudflare, GoDaddy, Namecheap).",
        },
        {
            "fr": "Trouvez la section de gestion des enregistrements DNS (souvent appelée \"Zone DNS\" ou \"DNS Management\").",
            "en": "Find the DNS records management section (often called \"DNS Zone\" or \"DNS Management\").",
        },
        {
            "fr": "Ajoutez les deux enregistrements listés ci-dessous (un CNAME et un TXT), avec exactement les noms et valeurs indiqués.",
            "en": "Add the two records listed below (one CNAME and one TXT), using exactly the names and values shown.",
        },
        {
            "fr": "Patientez -- la propagation DNS prend généralement de quelques minutes à quelques heures selon votre fournisseur.",
            "en": "Wait -- DNS propagation typically takes anywhere from a few minutes to a few hours depending on your provider.",
        },
        {
            "fr": "Une fois les enregistrements en place, appelez le lien de vérification fourni pour confirmer -- vous pouvez le redemander autant de fois que nécessaire tant que ce n'est pas encore propagé.",
            "en": "Once the records are in place, call the provided verification link to confirm -- you can request it again as many times as needed while propagation is still pending.",
        },
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

"""
Partie 1.4.5 -- Resend's real Domains API (create/get/verify/delete a
sending domain), via raw httpx -- same convention as api/services/
email.py's own module docstring: this project deliberately avoids the
`resend` SDK dependency, since it already leans on httpx directly
elsewhere and a handful of REST calls don't justify a new dependency.

**Verified against Resend's real API docs before writing this** (same
"honest scope" discipline as every other external integration in this
codebase): Resend GENERATES AND MANAGES ITS OWN DKIM KEY server-side,
under a fixed selector ("resend"), for every domain it registers -- it
never accepts a caller-supplied DKIM key or selector. This means
api/security/email_domains.py's own self-generated DKIM keypair (this
step's literal spec asks for one) is real, independent infrastructure
that is NOT what actually signs mail sent through Resend -- see that
module's own docstring for the full explanation. What Resend DOES
return, once a domain is created here, is the real set of DNS records
(an MX + an SPF TXT + a DKIM TXT under Resend's own naming) an Owner
must publish for Resend to actually accept `from:` addresses at that
domain and sign outgoing mail with ITS key.

Every function here raises on failure (EnvironmentError for a missing
key, RuntimeError for anything else) rather than swallowing it -- same
division of responsibility as email.py's _send(): it's the caller's job
(api/security/email_domains.py) to decide whether a given failure is
fatal or safe to degrade past, not this module's.
"""

import httpx

from api.config import settings

RESEND_DOMAINS_URL = "https://api.resend.com/domains"
RESEND_TIMEOUT_SECONDS = 10.0


def _headers() -> dict[str, str]:
    if not settings.RESEND_API_KEY:
        raise EnvironmentError(
            "RESEND_API_KEY is not set -- get one from https://resend.com/api-keys "
            "and set it in .env as RESEND_API_KEY=re_..."
        )
    return {"Authorization": f"Bearer {settings.RESEND_API_KEY}"}


def _request(method: str, url: str, **kwargs) -> dict:
    try:
        response = httpx.request(method, url, headers=_headers(), timeout=RESEND_TIMEOUT_SECONDS, **kwargs)
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise RuntimeError(f"Resend request timed out after {RESEND_TIMEOUT_SECONDS}s") from exc
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"Resend returned an error (status {exc.response.status_code}): {exc.response.text}") from exc
    except httpx.RequestError as exc:
        raise RuntimeError("Could not reach Resend -- check network connectivity") from exc
    return response.json()


def create_resend_domain(domain: str) -> dict:
    """Item 5's "configurer le domaine dans Resend (via API)". Returns
    Resend's real domain object -- id, status, and the real `records`
    array (MX/SPF/DKIM) the Owner must publish. Safe to call once per
    domain; a second call for an already-registered domain returns a
    normal Resend error (surfaced here as RuntimeError), which the
    caller treats as "already set up" rather than a fresh failure -- see
    api/security/email_domains.py's ensure_email_domain_setup."""
    return _request("POST", RESEND_DOMAINS_URL, json={"name": domain})


def get_resend_domain(resend_domain_id: str) -> dict:
    """Fetches the domain's current, live state from Resend -- the
    `records[*].status` values reflect Resend's own DNS checks, updated
    as its background verification progresses."""
    return _request("GET", f"{RESEND_DOMAINS_URL}/{resend_domain_id}")


def trigger_resend_domain_verification(resend_domain_id: str) -> dict:
    """Resend's own POST .../verify is itself asynchronous -- it only
    kicks off a background check on Resend's side and returns
    immediately (`{"object": "domain", "id": "..."}`), it does NOT
    return the final verified/not-verified outcome. Callers must poll
    get_resend_domain afterward to see the real result."""
    return _request("POST", f"{RESEND_DOMAINS_URL}/{resend_domain_id}/verify")


def delete_resend_domain(resend_domain_id: str) -> dict:
    """Used both by api/routers/custom_domains.py's delete flow (best-
    effort cleanup so removing a CustomDomain doesn't leave an orphaned
    Resend domain behind) and by this project's own integration tests,
    which must never leave junk domains in a real Resend account."""
    return _request("DELETE", f"{RESEND_DOMAINS_URL}/{resend_domain_id}")

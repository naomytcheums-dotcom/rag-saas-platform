"""
Partie 1.3.10 -- reading and writing an organization's branding. See
api/models/organization_branding.py's module docstring for why this is
a flat table of typed columns (like OrganizationQuota), not a JSON
override blob (like OrganizationSettings, Partie 1.3.9).

**Public by design, unlike every other /organizations/{org_id}/...
endpoint in this codebase**: GET is meant to power a PUBLIC-facing page
(a login screen, an embeddable widget) that a visitor reaches before
they're a member of anything, or even authenticated at all -- see
api/routers/organization_branding.py's own docstring for the
anti-enumeration tradeoff this deliberately accepts.
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.organization_branding import OrganizationBranding
from api.services import cache_service

# Étape 15 (Branding frontend) -- get_org_branding is now a real
# hot-path: every dashboard page load calls it once (BrandingApplier),
# on top of its own pre-existing public callers (login screen, widget).
# Same reasoning/TTL as api/security/organization_settings.py's own
# _ORG_SETTINGS_CACHE_TTL_SECONDS (Étape 13) -- short enough that an
# Owner changing a color takes effect within a minute even on a cache
# hit, long enough to absorb the new per-page-load read volume.
_ORG_BRANDING_CACHE_TTL_SECONDS = 60


def _cache_key(organization_id: uuid.UUID) -> str:
    return f"org_branding:{organization_id}"


DEFAULT_BRANDING: dict[str, Any] = {
    "logo_url": None,
    "favicon_url": None,
    "primary_color": "#2563eb",
    "secondary_color": "#1e293b",
    "accent_color": "#f59e0b",
    "font_family": "Inter",
    "brand_name": None,
    "custom_css": None,
    # Partie 1.4.6 -- see api/models/organization_branding.py's own
    # comment on this column.
    "hide_platform_branding": False,
    # Partie 19 -- white-label extension, see the model's own docstring.
    "company_email": None,
    "support_email": None,
    "email_sender_name": None,
    "email_sender_email": None,
    "custom_js": None,
    "is_active": True,
}

# Real, substantive checks against a stored-CSS-injection class of
# attack, not a placeholder: custom_css is OWNER-controlled but served
# to every anonymous visitor of that organization's public branded page
# (GET .../branding is public) -- CSS itself can't run arbitrary JS in
# a modern browser, but historically-exploitable constructs
# (`expression()` on old IE, `-moz-binding`/`behavior:` binding a
# stylesheet to script, `@import` silently fetching a third-party
# stylesheet that could fingerprint or track a visitor) are rejected
# outright rather than trusted because "it's just CSS."
_DANGEROUS_CSS_PATTERNS = ("javascript:", "expression(", "-moz-binding", "behavior:", "@import", "<script", "</style")
MAX_CUSTOM_CSS_LENGTH = 20_000


def validate_custom_css(css: str) -> None:
    lowered = css.lower()
    for pattern in _DANGEROUS_CSS_PATTERNS:
        if pattern in lowered:
            raise ValueError(f"custom_css contains a disallowed pattern: {pattern!r}")


# Partie 19 -- custom_js is NOT sanitized the way custom_css is above.
# There is no meaningful pattern-based sanitization for arbitrary
# JavaScript (unlike CSS's narrow, historically-exploitable construct
# list) -- a script IS arbitrary code by definition. The real security
# boundary is who can set it (require_org_owner, same as every other
# branding field) and where it runs (only this org's OWN white-labeled
# page, never the platform's own pages or another organization's) --
# the same trust model as an org owner embedding any third-party widget
# script on their own site. Only a real length bound is enforced here.
MAX_CUSTOM_JS_LENGTH = 20_000


def validate_custom_js(js: str) -> None:
    if len(js) > MAX_CUSTOM_JS_LENGTH:
        raise ValueError(f"custom_js exceeds the maximum length of {MAX_CUSTOM_JS_LENGTH} characters")


class InvalidSenderError(ValueError):
    """The e-mail sender identity an organization asked for may not be used (answered 400 by the application-wide handler in api/main.py)."""


_FORBIDDEN_SENDER_NAME_CHARACTERS = frozenset(chr(c) for c in (60, 62, 34, 13, 10, 9))  # < > " CR LF TAB


async def validate_email_sender(db: AsyncSession, organization_id: uuid.UUID, *, name: str | None, email: str | None) -> None:
    """1.4.9 -- who an organization's e-mails may claim to come from.

    The sender address is used verbatim as the `From` of the e-mails sent through the platform's mail provider account. Accepting any address would let an
    organization impersonate anyone, including the platform itself or any domain that account has verified. An address is therefore accepted only at a
    domain the organization has registered (1.4.1) AND proven it controls for e-mail (1.4.5, `email_verified`). The display name may not carry the characters
    that let it pose as a second address ("Boss <ceo@bank.com>") or break the header."""
    if name is not None and (not name.strip() or any(ch in _FORBIDDEN_SENDER_NAME_CHARACTERS for ch in name)):
        raise InvalidSenderError('The sender name must not be empty or contain < > " or line breaks')
    if email is None:
        return
    from api.models.custom_domain import CustomDomain

    if email.count("@") != 1:
        raise InvalidSenderError("The sender address is not a valid e-mail address")
    domain = email.rsplit("@", 1)[1].strip().lower()
    row = await db.scalar(select(CustomDomain).where(
        CustomDomain.organization_id == organization_id, CustomDomain.domain == domain, CustomDomain.email_verified.is_(True),
    ))
    if row is not None and row.resend_domain_id and settings.RESEND_API_KEY:
        # Ownership is proven; the mail provider must also accept the domain, otherwise every e-mail of the organization (invitations, notices) would be refused
        # at send time. Checked against the provider's own status, not assumed.
        import asyncio

        from api.services.resend_domains import get_resend_domain

        try:
            provider_status = (await asyncio.to_thread(get_resend_domain, row.resend_domain_id)).get("status")
        except (RuntimeError, EnvironmentError) as exc:
            raise InvalidSenderError(f"The mail provider could not confirm the domain '{domain}' right now ({type(exc).__name__}); try again in a moment") from exc
        if provider_status != "verified":
            raise InvalidSenderError(
                f"The mail provider has not verified '{domain}' yet (status: {provider_status}): publish the DNS records listed by "
                "GET .../domains/{domain_id}/email/dns, request the verification again, then choose the sender address"
            )
    if row is None:
        raise InvalidSenderError(
            f"'{domain}' is not a domain of this organization with a verified e-mail setup: register it (POST /organizations/{{org_id}}/domains) "
            "and verify it for e-mail (POST .../domains/{domain_id}/email/verify) before using it as the sender address"
        )


async def clear_sender_for_domain(db: AsyncSession, organization_id: uuid.UUID, domain: str) -> bool:
    """A domain is being removed: a sender address at that domain can no longer be vouched for, so the sender identity is cleared (the platform default applies
    again) rather than left pointing at a domain the organization no longer holds. Returns whether it was cleared."""
    row = await db.scalar(select(OrganizationBranding).where(OrganizationBranding.organization_id == organization_id))
    if row is None or not row.email_sender_email or row.email_sender_email.rsplit("@", 1)[-1].strip().lower() != domain.strip().lower():
        return False
    row.email_sender_email = None
    row.email_sender_name = None
    await db.flush()
    await cache_service.invalidate(_cache_key(organization_id))
    return True


def get_default_branding() -> dict[str, Any]:
    """Item 2's literal function -- a fresh copy each call, so a caller
    mutating the result never corrupts the module-level DEFAULT_BRANDING."""
    return dict(DEFAULT_BRANDING)


def _to_dict(row: OrganizationBranding) -> dict[str, Any]:
    return {
        "logo_url": row.logo_url, "favicon_url": row.favicon_url, "primary_color": row.primary_color,
        "secondary_color": row.secondary_color, "accent_color": row.accent_color, "font_family": row.font_family,
        "brand_name": row.brand_name, "custom_css": row.custom_css,
        "hide_platform_branding": row.hide_platform_branding,
        "company_email": row.company_email, "support_email": row.support_email,
        "email_sender_name": row.email_sender_name, "email_sender_email": row.email_sender_email,
        "custom_js": row.custom_js, "is_active": row.is_active,
    }


async def create_default_branding(db: AsyncSession, *, organization_id: uuid.UUID) -> OrganizationBranding:
    """Called once, at organization creation
    (api/security/organizations.py's create_organization_with_owner) --
    does NOT commit, same convention as create_default_quota/
    create_default_settings, so it's part of the SAME transaction as the
    organization and its founding Owner membership."""
    branding = OrganizationBranding(organization_id=organization_id)
    db.add(branding)
    await db.flush()
    return branding


async def get_org_branding(db: AsyncSession, organization_id: uuid.UUID) -> dict[str, Any]:
    """
    Item 2's literal function. `None` if no row exists (an organization
    created before this migration, or whose row was deleted out of
    band) falls back to pure defaults rather than raising -- same "fail
    toward the configured defaults" reasoning as
    api/security/quotas.py's get_quota_limits and
    api/security/organization_settings.py's get_org_settings, so a
    pre-existing org isn't suddenly broken by a step added after it
    already existed.
    """
    async def _load() -> dict[str, Any]:
        row = await db.scalar(select(OrganizationBranding).where(OrganizationBranding.organization_id == organization_id))
        if row is None:
            return dict(DEFAULT_BRANDING)
        return _to_dict(row)

    return await cache_service.get_or_set(_cache_key(organization_id), _load, ttl_seconds=_ORG_BRANDING_CACHE_TTL_SECONDS)


async def update_org_branding(db: AsyncSession, organization_id: uuid.UUID, updates: dict[str, Any]) -> dict[str, Any]:
    """
    Item 2's literal function -- a partial update: only the keys present
    in `updates` change. Type/format validation (hex colors, custom_css
    safety, URL fields untouched here since those are only ever set by
    the upload endpoints, never PATCH) happens one layer up, in
    api/schemas/organization_branding.py -- this function trusts its
    caller the same way every other *_settings/quotas update function
    in this codebase does.

    Does not commit -- same convention as every other security-layer
    write function in this codebase (the caller decides the transaction
    boundary).
    """
    row = await db.scalar(select(OrganizationBranding).where(OrganizationBranding.organization_id == organization_id))
    if row is None:
        # An organization that predates this migration, or whose row
        # was deleted out of band -- create it now rather than 404ing
        # an Owner who's allowed to be here (same reasoning as
        # api/routers/quotas.py's update_organization_quotas).
        row = OrganizationBranding(organization_id=organization_id)
        db.add(row)
        await db.flush()

    if updates.get("email_sender_email") is not None or updates.get("email_sender_name") is not None:
        await validate_email_sender(db, organization_id, name=updates.get("email_sender_name"), email=updates.get("email_sender_email"))
    for field, value in updates.items():
        setattr(row, field, value)
    await db.flush()
    # Same reasoning as organization_settings.py's own update path:
    # invalidate now, not after the caller's eventual commit, so a
    # second read within the same request never sees the pre-update
    # cached value.
    await cache_service.invalidate(_cache_key(organization_id))
    return _to_dict(row)

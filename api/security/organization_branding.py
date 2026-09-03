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

from api.models.organization_branding import OrganizationBranding

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
    row = await db.scalar(select(OrganizationBranding).where(OrganizationBranding.organization_id == organization_id))
    if row is None:
        return dict(DEFAULT_BRANDING)
    return _to_dict(row)


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

    for field, value in updates.items():
        setattr(row, field, value)
    await db.flush()
    return _to_dict(row)

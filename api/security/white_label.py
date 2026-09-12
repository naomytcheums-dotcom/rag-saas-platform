"""
Partie 1.4.6 -- white-label: letting an organization fully hide this
platform's own name/logo/legal mentions in favor of its own.

**Deliberately does NOT add a second, independent
`hide_platform_branding` key to organization_settings**, despite this
step's own action item 2 asking for one "pour garder la cohérence".
Reasoned through, not skipped silently: organization_settings (Partie
1.3.9) has no per-setting DATABASE COLUMN to add at all -- it's a single
generic JSON `settings` blob, keys merged with DEFAULT_SETTINGS at read
time (api/models/organization_settings.py's own docstring). Adding
`hide_platform_branding` there as a 15th override key would create a
SECOND, independent source of truth for the exact same boolean already
living on organization_branding (this step's item 1) -- two flags that
could silently disagree, with no mechanism keeping them in sync. Since
`hide_platform_branding` is fundamentally about BRANDING (it lives right
next to brand_name/logo_url/favicon_url, the exact things it toggles the
visibility of), organization_branding is the one, coherent home for it.

This module itself is a thin, honestly-thin layer: white-label config
IS branding config (branding already carries every field a frontend
needs to actually render the "hidden" state -- see get_white_label_config
below) -- not a parallel system with its own storage.

Partie 19 extends this with the full white-label surface (domain,
email sender identity, logo/favicon upload delegation, preview, reset)
-- still against organization_branding + CustomDomain, the SAME reason
as above: Partie 19's own spec asked for a new `WhiteLabelConfig`
model, but almost every field it named already existed on one of those
two tables. See api/models/organization_branding.py's own docstring
for the full accounting of what's genuinely new vs already real.
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.custom_domain import CustomDomain, CustomDomainStatus
from api.security.custom_domains import add_custom_domain, trigger_manual_verification
from api.security.organization_branding import DEFAULT_BRANDING, get_org_branding, update_org_branding
from api.services.storage import delete_branding_asset, upload_organization_favicon, upload_organization_logo


class WhiteLabelError(Exception):
    pass


class DomainNotFoundError(WhiteLabelError):
    pass


async def is_white_label_enabled(db: AsyncSession, organization_id: uuid.UUID) -> bool:
    """Item 3's literal function."""
    branding = await get_org_branding(db, organization_id)
    return branding["hide_platform_branding"]


async def get_white_label_config(db: AsyncSession, organization_id: uuid.UUID) -> dict[str, Any]:
    """Item 3's literal function -- "branding + hide flag". Returns the
    SAME dict api/routers/organization_branding.py's public GET
    .../branding already returns (hide_platform_branding is one of its
    keys, see api/security/organization_branding.py's DEFAULT_BRANDING)
    -- a dedicated name/endpoint for the white-label FEATURE, not a
    second, different shape of the same data. Kept as-is (pre-Partie
    19) for the pre-existing GET/PATCH .../white-label endpoints --
    get_whitelabel_config below is the Partie 19 superset."""
    return await get_org_branding(db, organization_id)


async def update_white_label(db: AsyncSession, organization_id: uuid.UUID, hide_platform_branding: bool) -> dict[str, Any]:
    """Item 4's literal PATCH -- delegates to update_org_branding with
    ONLY this one field, rather than re-implementing partial-update
    logic already correct there. Deliberately does not accept any other
    branding field here (colors, custom_css, etc. already have their own
    endpoint, PATCH .../branding) -- this endpoint's whole purpose is
    the white-label toggle, not a second way to edit the same colors."""
    return await update_org_branding(db, organization_id, {"hide_platform_branding": hide_platform_branding})


async def _get_latest_domain(db: AsyncSession, organization_id: uuid.UUID) -> CustomDomain | None:
    """Unlike api/security/custom_domains.py's own get_org_domain (ACTIVE
    only, for routing/display purposes), white-label's own config view
    needs to show a domain that's still `pending`/`failed` too, so the
    dashboard can render its real current status rather than showing
    nothing until it happens to succeed."""
    return await db.scalar(
        select(CustomDomain).where(CustomDomain.organization_id == organization_id).order_by(CustomDomain.created_at.desc())
    )


async def get_whitelabel_config(db: AsyncSession, organization_id: uuid.UUID) -> dict[str, Any]:
    """The full Partie 19 config: every real organization_branding field
    plus the org's own domain/domain_verified, read through from
    CustomDomain -- one real answer, not two things that could
    disagree."""
    branding = await get_org_branding(db, organization_id)
    domain_row = await _get_latest_domain(db, organization_id)
    branding["domain"] = domain_row.domain if domain_row else None
    branding["domain_verified"] = domain_row.status in (CustomDomainStatus.verified.value, CustomDomainStatus.active.value) if domain_row else False
    return branding


async def update_whitelabel_config(db: AsyncSession, organization_id: uuid.UUID, data: dict[str, Any], user_id: uuid.UUID | None = None) -> dict[str, Any]:
    """Partial update over the same real fields PATCH .../branding
    already exposes, plus the Partie 19 additions (contact emails,
    custom_js, is_active) -- never domain/logo/favicon, which have
    their own dedicated functions below (a file upload or a DNS-backed
    domain isn't a plain PATCH field). `user_id` isn't written anywhere
    today (there's no white-label audit trail yet) -- accepted for a
    stable signature if one is added later, same as several *_settings
    update functions elsewhere in this codebase already do."""
    del user_id
    allowed_fields = {
        "primary_color", "secondary_color", "accent_color", "font_family", "brand_name", "custom_css",
        "hide_platform_branding", "company_email", "support_email", "email_sender_name", "email_sender_email",
        "custom_js", "is_active",
    }
    updates = {k: v for k, v in data.items() if k in allowed_fields}
    await update_org_branding(db, organization_id, updates)
    return await get_whitelabel_config(db, organization_id)


async def set_custom_domain(db: AsyncSession, organization_id: uuid.UUID, domain: str, user_id: uuid.UUID | None = None) -> dict[str, Any]:
    del user_id
    await add_custom_domain(db, organization_id, domain)  # raises ValueError on an invalid/duplicate domain -- same real validation as Partie 1.4.1
    return await get_whitelabel_config(db, organization_id)


async def verify_domain(db: AsyncSession, organization_id: uuid.UUID) -> dict[str, Any]:
    domain_row = await _get_latest_domain(db, organization_id)
    if domain_row is None:
        raise DomainNotFoundError("This organization has no domain configured yet")
    await trigger_manual_verification(db, domain_row)
    return await get_whitelabel_config(db, organization_id)


async def remove_custom_domain(db: AsyncSession, organization_id: uuid.UUID, user_id: uuid.UUID | None = None) -> dict[str, Any]:
    del user_id
    domain_row = await _get_latest_domain(db, organization_id)
    if domain_row is None:
        raise DomainNotFoundError("This organization has no domain configured")
    await db.delete(domain_row)
    await db.flush()
    return await get_whitelabel_config(db, organization_id)


async def configure_email(db: AsyncSession, organization_id: uuid.UUID, *, sender_name: str | None, sender_email: str | None, user_id: uuid.UUID | None = None) -> dict[str, Any]:
    del user_id
    await update_org_branding(db, organization_id, {"email_sender_name": sender_name, "email_sender_email": sender_email})
    return await get_whitelabel_config(db, organization_id)


async def remove_email_config(db: AsyncSession, organization_id: uuid.UUID, user_id: uuid.UUID | None = None) -> dict[str, Any]:
    del user_id
    await update_org_branding(db, organization_id, {"email_sender_name": None, "email_sender_email": None})
    return await get_whitelabel_config(db, organization_id)


async def upload_logo(db: AsyncSession, organization_id: uuid.UUID, content: bytes, user_id: uuid.UUID | None = None) -> dict[str, Any]:
    """Delegates the real S3 upload/validation to
    api/services/storage.py's own upload_organization_logo -- the exact
    same function api/routers/organization_branding.py's own upload
    endpoint calls. Not reimplemented here."""
    del user_id
    current = await get_org_branding(db, organization_id)
    url = upload_organization_logo(organization_id, content)
    await update_org_branding(db, organization_id, {"logo_url": url})
    if current["logo_url"]:
        delete_branding_asset(current["logo_url"])
    return await get_whitelabel_config(db, organization_id)


async def remove_logo(db: AsyncSession, organization_id: uuid.UUID, user_id: uuid.UUID | None = None) -> dict[str, Any]:
    del user_id
    current = await get_org_branding(db, organization_id)
    await update_org_branding(db, organization_id, {"logo_url": None})
    if current["logo_url"]:
        delete_branding_asset(current["logo_url"])
    return await get_whitelabel_config(db, organization_id)


async def upload_favicon(db: AsyncSession, organization_id: uuid.UUID, content: bytes, user_id: uuid.UUID | None = None) -> dict[str, Any]:
    del user_id
    current = await get_org_branding(db, organization_id)
    url = upload_organization_favicon(organization_id, content)
    await update_org_branding(db, organization_id, {"favicon_url": url})
    if current["favicon_url"]:
        delete_branding_asset(current["favicon_url"])
    return await get_whitelabel_config(db, organization_id)


async def get_whitelabel_preview(db: AsyncSession, organization_id: uuid.UUID) -> dict[str, Any]:
    """Item 9's literal function -- the SAME real config a live
    dashboard preview needs, with is_active's own kill-switch already
    applied: an inactive config previews as pure platform defaults
    (+ the real domain/domain_verified, which aren't gated by
    is_active -- a verified custom domain stays a real fact about this
    organization regardless of whether its VISUAL branding is
    currently toggled off)."""
    config = await get_whitelabel_config(db, organization_id)
    if not config["is_active"]:
        preview = dict(DEFAULT_BRANDING)
        preview["domain"] = config["domain"]
        preview["domain_verified"] = config["domain_verified"]
        return preview
    return config


async def reset_whitelabel(db: AsyncSession, organization_id: uuid.UUID, user_id: uuid.UUID | None = None) -> dict[str, Any]:
    """Item 10's literal function -- resets the VISUAL/branding fields
    to their real defaults (colors, name, custom_css/js, hide flag,
    contact emails). Deliberately excludes logo_url/favicon_url (an
    uploaded file stays uploaded -- clearing the pointer here without
    also deleting the real S3 object would just orphan it) and the
    custom domain -- "reset my branding" and "remove my logo"/"give up
    my domain" are different real decisions an Owner might not mean
    together; those already have their own dedicated, explicit
    endpoints."""
    del user_id
    reset_fields = {k: v for k, v in DEFAULT_BRANDING.items() if k not in ("logo_url", "favicon_url")}
    await update_org_branding(db, organization_id, reset_fields)
    return await get_whitelabel_config(db, organization_id)

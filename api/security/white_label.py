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
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from api.security.organization_branding import get_org_branding, update_org_branding


async def is_white_label_enabled(db: AsyncSession, organization_id: uuid.UUID) -> bool:
    """Item 3's literal function."""
    branding = await get_org_branding(db, organization_id)
    return branding["hide_platform_branding"]


async def get_white_label_config(db: AsyncSession, organization_id: uuid.UUID) -> dict[str, Any]:
    """
    Item 3's literal function -- "branding + hide flag". Returns the
    SAME dict api/routers/organization_branding.py's public GET
    .../branding already returns (hide_platform_branding is one of its
    keys, see api/security/organization_branding.py's DEFAULT_BRANDING)
    -- a dedicated name/endpoint for the white-label FEATURE, not a
    second, different shape of the same data.
    """
    return await get_org_branding(db, organization_id)


async def update_white_label(db: AsyncSession, organization_id: uuid.UUID, hide_platform_branding: bool) -> dict[str, Any]:
    """Item 4's literal PATCH -- delegates to update_org_branding with
    ONLY this one field, rather than re-implementing partial-update
    logic already correct there. Deliberately does not accept any other
    branding field here (colors, custom_css, etc. already have their own
    endpoint, PATCH .../branding) -- this endpoint's whole purpose is
    the white-label toggle, not a second way to edit the same colors."""
    return await update_org_branding(db, organization_id, {"hide_platform_branding": hide_platform_branding})

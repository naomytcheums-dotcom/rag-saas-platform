"""Request/response bodies for api/routers/white_label.py (Partie
1.4.6). Deliberately the SAME field set as
api/schemas/organization_branding.py's OrganizationBrandingResponse --
see api/security/white_label.py's own docstring for why white-label
config IS branding config, not a parallel shape."""

import uuid

from pydantic import BaseModel


class WhiteLabelConfigResponse(BaseModel):
    organization_id: uuid.UUID
    hide_platform_branding: bool
    logo_url: str | None
    favicon_url: str | None
    primary_color: str
    secondary_color: str
    accent_color: str
    font_family: str
    brand_name: str | None
    custom_css: str | None


class WhiteLabelUpdateRequest(BaseModel):
    """PATCH /organizations/{org_id}/white-label -- deliberately the
    ONLY field this endpoint can change (see
    api/security/white_label.py's update_white_label docstring).
    Optional with exclude_unset=True for the same partial-update
    convention every other PATCH in this codebase uses, even though
    there is only one field to set."""

    hide_platform_branding: bool | None = None

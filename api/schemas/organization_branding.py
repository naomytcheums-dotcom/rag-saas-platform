"""Request/response bodies for api/routers/organization_branding.py
(Partie 1.3.10)."""

import uuid

from pydantic import BaseModel, Field, field_validator

from api.security.organization_branding import MAX_CUSTOM_CSS_LENGTH, validate_custom_css

_HEX_COLOR_PATTERN = r"^#[0-9a-fA-F]{6}$"


class OrganizationBrandingResponse(BaseModel):
    organization_id: uuid.UUID
    logo_url: str | None
    favicon_url: str | None
    primary_color: str
    secondary_color: str
    accent_color: str
    font_family: str
    brand_name: str | None
    custom_css: str | None


class OrganizationBrandingUpdateRequest(BaseModel):
    """PATCH /organizations/{org_id}/branding -- every field optional,
    only the ones actually sent are changed (partial update, same
    exclude_unset=True convention as every other *_settings/quotas
    update request in this codebase). Deliberately does NOT include
    logo_url/favicon_url -- those are only ever set by the dedicated
    upload endpoints (which validate the actual file), never as a
    caller-supplied string PATCH could otherwise point at an arbitrary,
    unvalidated URL."""

    primary_color: str | None = Field(default=None, pattern=_HEX_COLOR_PATTERN, description="Hex color, e.g. '#2563eb'")
    secondary_color: str | None = Field(default=None, pattern=_HEX_COLOR_PATTERN)
    accent_color: str | None = Field(default=None, pattern=_HEX_COLOR_PATTERN)
    font_family: str | None = Field(default=None, min_length=1, max_length=100)
    brand_name: str | None = Field(default=None, max_length=200)
    custom_css: str | None = Field(default=None, max_length=MAX_CUSTOM_CSS_LENGTH)

    @field_validator("custom_css")
    @classmethod
    def _validate_custom_css(cls, value: str | None) -> str | None:
        if value is not None:
            validate_custom_css(value)
        return value

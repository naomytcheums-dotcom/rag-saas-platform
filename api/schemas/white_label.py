"""Request/response bodies for api/routers/white_label.py (Partie
1.4.6). Deliberately the SAME field set as
api/schemas/organization_branding.py's OrganizationBrandingResponse --
see api/security/white_label.py's own docstring for why white-label
config IS branding config, not a parallel shape."""

import uuid

from pydantic import BaseModel, EmailStr, Field, field_validator

from api.security.organization_branding import (
    MAX_CUSTOM_CSS_LENGTH, MAX_CUSTOM_JS_LENGTH, validate_custom_css, validate_custom_js,
)

_HEX_COLOR_PATTERN = r"^#[0-9a-fA-F]{6}$"


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


# -- Partie 19: the full white-label surface ---------------------------------
# Separate from the two classes above (kept as-is for the pre-existing
# GET/PATCH .../white-label endpoints) -- these back the new
# GET/PATCH .../whitelabel/config and friends, with the full field set
# api/security/white_label.py's get_whitelabel_config now returns.

class WhiteLabelFullConfigResponse(BaseModel):
    organization_id: uuid.UUID
    logo_url: str | None
    favicon_url: str | None
    primary_color: str
    secondary_color: str
    accent_color: str
    font_family: str
    brand_name: str | None
    custom_css: str | None
    custom_js: str | None
    hide_platform_branding: bool
    company_email: str | None
    support_email: str | None
    email_sender_name: str | None
    email_sender_email: str | None
    is_active: bool
    domain: str | None
    domain_verified: bool


class WhiteLabelFullUpdateRequest(BaseModel):
    """PATCH /organizations/{org_id}/whitelabel/config -- every field
    optional, partial update (exclude_unset=True, same convention as
    every other PATCH in this codebase). Deliberately excludes logo_url/
    favicon_url/domain -- those go through their own dedicated upload/
    domain endpoints below, same reasoning as
    OrganizationBrandingUpdateRequest's own docstring."""

    primary_color: str | None = Field(default=None, pattern=_HEX_COLOR_PATTERN)
    secondary_color: str | None = Field(default=None, pattern=_HEX_COLOR_PATTERN)
    accent_color: str | None = Field(default=None, pattern=_HEX_COLOR_PATTERN)
    font_family: str | None = Field(default=None, min_length=1, max_length=100)
    brand_name: str | None = Field(default=None, max_length=200)
    custom_css: str | None = Field(default=None, max_length=MAX_CUSTOM_CSS_LENGTH)
    custom_js: str | None = Field(default=None, max_length=MAX_CUSTOM_JS_LENGTH)
    hide_platform_branding: bool | None = None
    company_email: EmailStr | None = None
    support_email: EmailStr | None = None
    is_active: bool | None = None

    @field_validator("custom_css")
    @classmethod
    def _validate_custom_css(cls, value: str | None) -> str | None:
        if value is not None:
            validate_custom_css(value)
        return value

    @field_validator("custom_js")
    @classmethod
    def _validate_custom_js(cls, value: str | None) -> str | None:
        if value is not None:
            validate_custom_js(value)
        return value


class SetCustomDomainRequest(BaseModel):
    domain: str = Field(min_length=1, max_length=255)


class ConfigureEmailRequest(BaseModel):
    sender_name: str = Field(min_length=1, max_length=200)
    sender_email: EmailStr

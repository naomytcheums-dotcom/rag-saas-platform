"""Request/response bodies for api/routers/enterprise_sso.py (audit finding 27)."""

import datetime as dt
import uuid

from pydantic import BaseModel, EmailStr, Field


class EnterpriseSSOConnectionCreateRequest(BaseModel):
    """Body of POST /admin/sso/connections -- an admin configuring a new
    customer IdP. `issuer` must be the IdP's OIDC discovery issuer (e.g.
    "https://login.microsoftonline.com/{tenant-id}/v2.0" for Azure AD,
    "https://your-org.okta.com" for Okta) -- api/security/enterprise_oidc.py
    fetches {issuer}/.well-known/openid-configuration from it directly,
    never a value entered separately, so the two can't drift apart."""

    email_domain: str = Field(min_length=1, max_length=255)
    display_name: str = Field(min_length=1, max_length=200)
    issuer: str = Field(min_length=1, max_length=500)
    client_id: str = Field(min_length=1, max_length=255)
    client_secret: str = Field(min_length=1)


class EnterpriseSSOConnectionEntry(BaseModel):
    """Never includes the client secret -- see
    api/models/enterprise_sso.py's client_secret_encrypted column
    docstring."""

    id: uuid.UUID
    email_domain: str
    display_name: str
    issuer: str
    client_id: str
    is_enabled: bool
    created_at: dt.datetime

    model_config = {"from_attributes": True}


class EnterpriseSSOConnectionListResponse(BaseModel):
    items: list[EnterpriseSSOConnectionEntry]


class SSODiscoverRequest(BaseModel):
    """Body of POST /auth/sso/discover -- public, unauthenticated: lets
    the frontend's login screen show "Continue with <Company> SSO" the
    moment the user finishes typing their email, before any credentials
    are entered."""

    email: EmailStr


class SSODiscoverResponse(BaseModel):
    sso_available: bool
    connection_id: uuid.UUID | None = None
    display_name: str | None = None

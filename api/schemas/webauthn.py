"""Request/response bodies for api/routers/webauthn.py (audit finding 26)."""

import datetime as dt
import uuid

from pydantic import BaseModel, Field


class WebAuthnRegistrationVerifyRequest(BaseModel):
    """Body of POST /auth/webauthn/register/verify -- `credential` is the
    raw JSON object navigator.credentials.create() produced, passed
    through as-is to the `webauthn` library's own parser rather than
    modeled field by field here: its shape is defined by the WebAuthn
    spec, not by this app."""

    credential: dict
    nickname: str = Field(min_length=1, max_length=100)


class WebAuthnAuthenticationOptionsRequest(BaseModel):
    """Body of POST /auth/webauthn/authenticate/options -- the same
    mfa_token bridge as POST /auth/2fa/verify-login
    (api/schemas/auth.py's TwoFactorVerifyLoginRequest): proves the
    password already checked out, without a real session yet."""

    mfa_token: str


class WebAuthnAuthenticationVerifyRequest(BaseModel):
    """Body of POST /auth/webauthn/authenticate/verify."""

    mfa_token: str
    credential: dict


class WebAuthnCredentialEntry(BaseModel):
    """One row of GET /auth/webauthn/credentials -- never the raw
    credential_id or public_key. Neither is a secret, but neither is
    useful to a client either; leaving both out avoids tempting a future
    caller into treating either as if it were sensitive or actionable."""

    id: uuid.UUID
    nickname: str
    transports: str | None
    created_at: dt.datetime
    last_used_at: dt.datetime | None

    model_config = {"from_attributes": True}


class WebAuthnCredentialListResponse(BaseModel):
    items: list[WebAuthnCredentialEntry]

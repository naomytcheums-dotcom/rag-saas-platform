"""Schemas for api/routers/account.py and sessions.py (1.1.9, 1.1.13, 1.1.14)."""

import datetime as dt
import uuid
import zoneinfo

from pydantic import BaseModel, field_validator


class UserProfileResponse(BaseModel):
    """
    Returned by GET/PATCH /account/me and /account/profile,
    /account/preferences, /account/avatar -- the public-facing shape of a
    user's own profile. Deliberately excludes anything sensitive
    (hashed_password, totp_secret): this is built with
    `.model_validate(user)` from the ORM object, and only the fields
    listed here ever leave the server.
    """

    id: uuid.UUID
    email: str
    full_name: str | None
    company: str | None
    avatar_url: str | None
    locale: str
    timezone: str
    is_email_verified: bool
    totp_enabled: bool
    created_at: dt.datetime

    # Lets pydantic build this model directly from a SQLAlchemy User
    # instance's attributes (user.email, user.full_name, ...) instead of
    # requiring a dict -- what `UserProfileResponse.model_validate(user)`
    # relies on throughout api/routers/account.py.
    model_config = {"from_attributes": True}


class ProfileUpdateRequest(BaseModel):
    """Body of PATCH /account/profile. Both fields optional -- a field
    left out of the request body is left unchanged, not cleared."""

    full_name: str | None = None
    company: str | None = None


class PreferencesUpdateRequest(BaseModel):
    """Body of PATCH /account/preferences. Same "omit to leave unchanged"
    rule as ProfileUpdateRequest above."""

    locale: str | None = None
    timezone: str | None = None

    @field_validator("timezone")
    @classmethod
    def _valid_iana_timezone(cls, value: str | None) -> str | None:
        # Checked against Python's own bundled IANA timezone database --
        # rejects typos/garbage (e.g. "Europe/Pariss") before they're
        # ever stored, rather than silently accepting any string.
        if value is not None and value not in zoneinfo.available_timezones():
            raise ValueError(f"'{value}' is not a valid IANA timezone (e.g. 'Europe/Paris', 'Africa/Douala')")
        return value


class SessionResponse(BaseModel):
    """One row of GET /sessions' response list -- one active device/login."""

    id: uuid.UUID
    device_info: str | None  # raw User-Agent header captured at login, e.g. "Mozilla/5.0 (Windows NT..."
    ip_address: str | None
    created_at: dt.datetime
    last_seen_at: dt.datetime  # updated every time this session's refresh token is used
    is_current: bool  # True if this is the session the request itself was made with

    model_config = {"from_attributes": True}

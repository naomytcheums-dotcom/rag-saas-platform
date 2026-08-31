"""Schemas for api/routers/account.py and sessions.py (1.1.9, 1.1.13, 1.1.14)."""

import datetime as dt
import uuid
import zoneinfo

from pydantic import BaseModel, field_validator


class UserProfileResponse(BaseModel):
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

    model_config = {"from_attributes": True}


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = None
    company: str | None = None


class PreferencesUpdateRequest(BaseModel):
    locale: str | None = None
    timezone: str | None = None

    @field_validator("timezone")
    @classmethod
    def _valid_iana_timezone(cls, value: str | None) -> str | None:
        if value is not None and value not in zoneinfo.available_timezones():
            raise ValueError(f"'{value}' is not a valid IANA timezone (e.g. 'Europe/Paris', 'Africa/Douala')")
        return value


class SessionResponse(BaseModel):
    id: uuid.UUID
    device_info: str | None
    ip_address: str | None
    created_at: dt.datetime
    last_seen_at: dt.datetime
    is_current: bool

    model_config = {"from_attributes": True}

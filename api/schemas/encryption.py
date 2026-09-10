"""Request/response bodies for Partie 10.3 (encryption)."""

import datetime as dt

from pydantic import BaseModel


class EncryptionStatusResponse(BaseModel):
    enabled: bool
    algorithm: str
    key_storage: str
    encrypted_fields: list[str]
    encrypted_row_count: int
    previous_key_configured: bool
    last_rotation_at: dt.datetime | None


class EncryptionAlgorithmEntry(BaseModel):
    name: str
    purpose: str
    in_use: bool


class RotateKeysResponse(BaseModel):
    rotated_rows: int
    rotated_at: dt.datetime


class EncryptionTestResponse(BaseModel):
    roundtrip_ok: bool
    hash_verification_ok: bool
    algorithm: str

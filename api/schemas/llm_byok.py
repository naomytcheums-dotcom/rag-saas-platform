"""BYOK (Bring Your Own Key) request/response shapes."""

import datetime as dt
import uuid

from pydantic import BaseModel, Field


class LLMConfigSetRequest(BaseModel):
    provider: str
    api_key: str = Field(min_length=1, max_length=500)


class LLMConfigResponse(BaseModel):
    """Never carries the real key or its ciphertext -- only enough for
    the UI to show "a key is configured for this provider" and let the
    org replace or remove it."""

    id: uuid.UUID
    provider: str
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime

    model_config = {"from_attributes": True}

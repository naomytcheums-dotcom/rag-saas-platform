"""Request/response bodies for api/routers/custom_tools.py (Partie 5.2.10).

`schema_`'s own JSON key stays `schema` (item 1's own literal field
name) via a real Pydantic alias -- a plain field named `schema` works
in Pydantic but shadows `BaseModel.schema()` (a real, deprecated
classmethod), same real "alias around a name Pydantic itself already
uses" reasoning as `api/schemas/agents.py`'s own `model_config` alias."""

import datetime as dt
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CustomToolCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    description: str = ""
    webhook_url: str
    method: str = "POST"
    headers: dict | None = None
    timeout: int = 20
    retry_count: int = 1
    schema_: dict = Field(default_factory=dict, alias="schema")


class CustomToolUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = None
    description: str | None = None
    webhook_url: str | None = None
    method: str | None = None
    headers: dict | None = None
    timeout: int | None = None
    retry_count: int | None = None
    schema_: dict | None = Field(default=None, alias="schema")


class CustomToolResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: str
    webhook_url: str
    method: str
    headers: dict | None
    timeout: int
    retry_count: int
    schema_: dict = Field(validation_alias="schema", serialization_alias="schema")
    created_by: uuid.UUID | None
    created_at: dt.datetime
    updated_at: dt.datetime


class CustomToolExecuteRequest(BaseModel):
    params: dict = Field(default_factory=dict)


class CustomToolExecuteResponse(BaseModel):
    status_code: int
    headers: dict
    body: Any

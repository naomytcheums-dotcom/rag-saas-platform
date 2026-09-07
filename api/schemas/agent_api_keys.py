"""Request/response bodies for api/routers/agent_api_keys.py (Partie 5.3.10).

`AgentAPIKeyResponse` (listing) deliberately has no `key`/`key_hash`
field -- the real plaintext key only ever appears once, in
`AgentAPIKeyCreateResponse`, the direct response of the generate
endpoint itself."""

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict


class AgentAPIKeyCreateRequest(BaseModel):
    name: str
    scopes: list[str]
    expires_at: dt.datetime | None = None


class AgentAPIKeyCreateResponse(BaseModel):
    id: uuid.UUID
    name: str
    key: str
    key_prefix: str
    scopes: list[str]
    expires_at: dt.datetime | None
    created_at: dt.datetime


class AgentAPIKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    key_prefix: str
    scopes: list
    expires_at: dt.datetime | None
    last_used_at: dt.datetime | None
    created_at: dt.datetime
    revoked_at: dt.datetime | None


class AgentRunViaAPIKeyRequest(BaseModel):
    input: str
    context: str | None = None


class AgentRunViaAPIKeyResponse(BaseModel):
    run_id: uuid.UUID
    status: str
    result: str | None
    error: str | None

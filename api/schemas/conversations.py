"""Request/response bodies for api/routers/conversations.py (Partie 5.1.12)."""

import datetime as dt
import uuid

from pydantic import BaseModel, Field


class ConversationCreateRequest(BaseModel):
    agent_id: str
    title: str = Field(default="New conversation")
    organization_id: uuid.UUID | None = None


class ConversationResponse(BaseModel):
    id: uuid.UUID
    agent_id: str
    user_id: uuid.UUID
    title: str
    created_at: dt.datetime
    updated_at: dt.datetime
    archived: bool

    model_config = {"from_attributes": True}


class ConversationTitleUpdateRequest(BaseModel):
    title: str


class ConversationMessageCreateRequest(BaseModel):
    role: str = Field(pattern="^(user|assistant|system|tool)$")
    content: str
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None
    metadata: dict | None = None


class ConversationMessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    tool_calls: list[dict] | None
    tool_call_id: str | None
    created_at: dt.datetime

    model_config = {"from_attributes": True}

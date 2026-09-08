"""Request/response bodies for Partie 8.1.6/8.1.7/8.1.8/8.1.9's own
message-action endpoints (api/routers/conversations.py)."""

import datetime as dt
import uuid

from pydantic import BaseModel, Field

from api.schemas.conversations import ConversationMessageResponse


class RegenerateRequest(BaseModel):
    agent_id: str | None = None
    model_config_override: dict | None = Field(default=None, alias="model_config")

    model_config = {"populate_by_name": True}


class EditQuestionRequest(BaseModel):
    content: str


class EditAndRegenerateRequest(BaseModel):
    content: str


class RetryResponse(BaseModel):
    message: ConversationMessageResponse
    retry_count: int


class EditHistoryEntryResponse(BaseModel):
    id: uuid.UUID
    message_id: uuid.UUID
    version: int
    content: str
    edited_at: dt.datetime
    edited_by: uuid.UUID | None

    model_config = {"from_attributes": True}


class RevertRequest(BaseModel):
    version: int


class FeedbackCreateRequest(BaseModel):
    rating: str = Field(pattern="^(positive|negative)$")
    reason: str | None = None
    comment: str | None = None


class FeedbackUpdateRequest(BaseModel):
    rating: str | None = Field(default=None, pattern="^(positive|negative)$")
    reason: str | None = None
    comment: str | None = None


class FeedbackResponse(BaseModel):
    id: uuid.UUID
    message_id: uuid.UUID
    user_id: uuid.UUID
    rating: str
    reason: str | None
    comment: str | None
    created_at: dt.datetime

    model_config = {"from_attributes": True}


class FeedbackStatsResponse(BaseModel):
    total: int
    positive: int
    negative: int
    positive_rate: float | None

"""Request/response bodies for Partie 8.1.15/8.1.16."""

import datetime as dt
import uuid

from pydantic import BaseModel

from api.schemas.conversations import ConversationMessageResponse, ConversationResponse


class ShareCreateRequest(BaseModel):
    expires_at: dt.datetime | None = None
    max_views: int | None = None


class ShareResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    token: str
    shared_by: uuid.UUID
    expires_at: dt.datetime | None
    max_views: int | None
    views: int
    created_at: dt.datetime

    model_config = {"from_attributes": True}


class SharedConversationResponse(BaseModel):
    conversation: ConversationResponse
    messages: list[ConversationMessageResponse]


class VisibilityUpdateRequest(BaseModel):
    is_public: bool

"""Request/response bodies for Partie 8.1.10/8.1.11/8.1.12/8.1.13's own
conversation-management endpoints (api/routers/conversations.py)."""

import datetime as dt
import uuid

from pydantic import BaseModel

from api.schemas.conversations import ConversationMessageResponse, ConversationResponse


class ConversationStatsResponse(BaseModel):
    total_conversations: int
    archived_conversations: int
    total_messages: int


class SearchResultResponse(BaseModel):
    conversation: ConversationResponse
    matched_message: ConversationMessageResponse | None
    highlighted_snippet: str | None


class DeletedConversationResponse(ConversationResponse):
    deleted_at: dt.datetime | None

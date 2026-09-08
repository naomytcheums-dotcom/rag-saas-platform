"""Request body for api/routers/chat_stream.py (Partie 8.1.1)."""

import uuid

from pydantic import BaseModel


class ChatStreamRequest(BaseModel):
    agent_id: uuid.UUID
    message: str
    conversation_id: uuid.UUID | None = None

"""Request/response bodies for Partie 8.1.17/8.1.18."""

import datetime as dt
import uuid

from pydantic import BaseModel


class SuggestedQuestionsResponse(BaseModel):
    questions: list[str]


class FollowUpQuestionGenerateRequest(BaseModel):
    count: int | None = None


class FollowUpQuestionResponse(BaseModel):
    id: uuid.UUID
    message_id: uuid.UUID
    question: str
    clicked: bool
    created_at: dt.datetime

    model_config = {"from_attributes": True}

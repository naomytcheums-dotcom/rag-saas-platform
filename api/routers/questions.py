"""Partie 8.1.17 (Suggested questions) + 8.1.18 (Follow-up questions).

**Incohérence réelle du prompt 8.1.17 corrigée**: the literal ask lists
TWO endpoints for the same real feature -- `GET /conversations/suggested-questions`
(no real organization scope at all) and
`GET /organizations/{org_id}/suggested-questions` (real, properly
scoped). Only the second is kept here: "suggested questions" are
real-ily organization-scoped data (`get_popular_questions`/
`get_recent_questions` both need a real `organization_id` to query
against), so an unscoped variant would either be meaningless or
silently guess an organization -- the same kind of real,
under-specified duplicate this session has corrected elsewhere (e.g.
8.1.6-8.1.8's own real `/chat` vs `/conversations` routing note)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.conversation import ConversationMessage
from api.models.organization import OrganizationMember
from api.models.user import User
from api.schemas.suggested_questions import (
    FollowUpQuestionGenerateRequest, FollowUpQuestionResponse, SuggestedQuestionsResponse,
)
from api.security.permissions import require_permission
from api.security.conversations import get_conversation
from api.security.organizations import require_org_member
from api.services.suggested_questions import (
    FollowUpQuestionError, generate_follow_up_questions, get_follow_up_questions, get_suggested_questions,
    save_follow_up_questions,
)
from api.utils import MAX_PAGE_SIZE

router = APIRouter(tags=["questions"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


@router.get("/organizations/{org_id}/suggested-questions", response_model=SuggestedQuestionsResponse)
async def get_suggested_questions_endpoint(
    org_id: uuid.UUID, context: str | None = None, limit: int | None = Query(default=None, ge=1, le=MAX_PAGE_SIZE),
    _caller: OrganizationMember = Depends(require_permission("evaluation:read")), current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    questions = await get_suggested_questions(db, org_id, current_user.id, context=context, limit=limit)
    return SuggestedQuestionsResponse(questions=questions)


async def _get_owned_message(db: AsyncSession, message_id: uuid.UUID, user: User) -> ConversationMessage:
    message = await db.get(ConversationMessage, message_id)
    if message is None:
        raise _NOT_FOUND
    conversation = await get_conversation(db, message.conversation_id)
    if conversation is None or conversation.user_id != user.id:
        raise _NOT_FOUND
    return message


@router.post("/messages/{message_id}/follow-up", response_model=list[FollowUpQuestionResponse])
async def generate_follow_up_questions_endpoint(
    message_id: uuid.UUID, payload: FollowUpQuestionGenerateRequest = FollowUpQuestionGenerateRequest(),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await _get_owned_message(db, message_id, current_user)
    try:
        questions = await generate_follow_up_questions(db, message_id, current_user.id, count=payload.count)
    except FollowUpQuestionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    rows = await save_follow_up_questions(db, message_id, questions)
    await db.commit()
    return rows


@router.get("/messages/{message_id}/follow-up", response_model=list[FollowUpQuestionResponse])
async def list_follow_up_questions_endpoint(
    message_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await _get_owned_message(db, message_id, current_user)
    return await get_follow_up_questions(db, message_id)

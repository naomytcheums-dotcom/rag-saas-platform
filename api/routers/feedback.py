"""Partie 8.1.9 -- 👍/👎 feedback on individual conversation messages.

Real ownership-based access on the message-level routes (same
reasoning as `api/routers/conversations.py`'s own docstring: a message
lives inside a personal conversation) -- `_get_owned_message` loads the
real message AND its real parent conversation, 404 for anyone else's.
The organization-wide stats route is the one real exception (an
aggregate across every member's own feedback, not one person's), so it
uses `require_org_admin` instead."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.conversation import ConversationMessage
from api.models.organization import OrganizationMember
from api.models.user import User
from api.schemas.message_actions import (
    FeedbackCreateRequest, FeedbackResponse, FeedbackStatsResponse, FeedbackUpdateRequest,
)
from api.security.permissions import require_permission
from api.security.conversations import get_conversation
from api.security.organizations import require_org_admin
from api.services.message_actions import MessageActionError, add_feedback, delete_feedback, get_feedback, get_feedback_stats, update_feedback

router = APIRouter(tags=["feedback"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


async def _get_owned_message(db: AsyncSession, message_id: uuid.UUID, user: User) -> ConversationMessage:
    message = await db.get(ConversationMessage, message_id)
    if message is None:
        raise _NOT_FOUND
    conversation = await get_conversation(db, message.conversation_id)
    if conversation is None or conversation.user_id != user.id:
        raise _NOT_FOUND
    return message


@router.post("/messages/{message_id}/feedback", response_model=FeedbackResponse)
async def add_feedback_endpoint(
    message_id: uuid.UUID, payload: FeedbackCreateRequest,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await _get_owned_message(db, message_id, current_user)
    try:
        feedback = await add_feedback(db, message_id, current_user.id, payload.rating, reason=payload.reason, comment=payload.comment)
    except MessageActionError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    return feedback


@router.get("/messages/{message_id}/feedback", response_model=list[FeedbackResponse])
async def list_feedback_endpoint(
    message_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await _get_owned_message(db, message_id, current_user)
    return await get_feedback(db, message_id)


@router.patch("/feedback/{feedback_id}", response_model=FeedbackResponse)
async def update_feedback_endpoint(
    feedback_id: uuid.UUID, payload: FeedbackUpdateRequest,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    from api.models.message_actions import MessageFeedback

    existing = await db.get(MessageFeedback, feedback_id)
    if existing is None or existing.user_id != current_user.id:
        raise _NOT_FOUND
    try:
        feedback = await update_feedback(db, feedback_id, rating=payload.rating, reason=payload.reason, comment=payload.comment)
    except MessageActionError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    return feedback


@router.delete("/feedback/{feedback_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feedback_endpoint(
    feedback_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    from api.models.message_actions import MessageFeedback

    existing = await db.get(MessageFeedback, feedback_id)
    if existing is None or existing.user_id != current_user.id:
        raise _NOT_FOUND
    await delete_feedback(db, feedback_id)
    await db.commit()


@router.get("/organizations/{org_id}/feedback/stats", response_model=FeedbackStatsResponse)
async def get_feedback_stats_endpoint(
    org_id: uuid.UUID, _caller: OrganizationMember = Depends(require_permission("conversations:manage")), db: AsyncSession = Depends(get_db),
):
    return await get_feedback_stats(db, org_id)

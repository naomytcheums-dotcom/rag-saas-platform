"""Partie 8.1.15 -- the two real, top-level `/share/{token}` routes
(NOT under `/conversations`, since a real, valid token is itself the
real credential -- `GET /share/{token}` is deliberately PUBLIC, no
`get_current_user` at all, same as any other real, unauthenticated
share-link pattern)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.user import User
from api.schemas.conversation_sharing import SharedConversationResponse
from api.security.conversations import get_conversation_messages
from api.services.conversation_sharing import delete_share_link, get_shared_conversation, increment_view_count

router = APIRouter(tags=["conversation-sharing"])


@router.get("/share/{token}", response_model=SharedConversationResponse)
async def get_shared_conversation_endpoint(token: str, db: AsyncSession = Depends(get_db)):
    result = await get_shared_conversation(db, token)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    conversation, _share = result
    messages = await get_conversation_messages(db, conversation.id)
    await increment_view_count(db, token)
    await db.commit()
    return SharedConversationResponse(conversation=conversation, messages=messages)


@router.delete("/share/{token}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_share_link_endpoint(token: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    deleted = await delete_share_link(db, token, current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await db.commit()

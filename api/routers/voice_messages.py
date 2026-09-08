"""Partie 8.2.7 -- Audio history. Real ownership-based access, same
pattern as api/routers/feedback.py: a voice message lives inside a
personal conversation."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.voice import VoiceMessage
from api.models.user import User
from api.schemas.voice_messages import VoiceMessageResponse
from api.security.conversations import get_conversation
from api.services.voice_messages import delete_voice_message, get_voice_message, get_voice_messages
from api.services.voice_storage import download_voice_recording

router = APIRouter(tags=["voice-messages"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


async def _get_owned_voice_message(db: AsyncSession, message_id: uuid.UUID, user: User) -> VoiceMessage:
    message = await get_voice_message(db, message_id)
    if message is None:
        raise _NOT_FOUND
    conversation = await get_conversation(db, message.conversation_id)
    if conversation is None or conversation.user_id != user.id:
        raise _NOT_FOUND
    return message


@router.get("/conversations/{conversation_id}/voice-messages", response_model=list[VoiceMessageResponse])
async def list_voice_messages_endpoint(
    conversation_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    conversation = await get_conversation(db, conversation_id)
    if conversation is None or conversation.user_id != current_user.id:
        raise _NOT_FOUND
    return await get_voice_messages(db, conversation_id)


@router.get("/voice-messages/{message_id}", response_model=VoiceMessageResponse)
async def get_voice_message_endpoint(
    message_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    return await _get_owned_voice_message(db, message_id, current_user)


@router.delete("/voice-messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_voice_message_endpoint(
    message_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await _get_owned_voice_message(db, message_id, current_user)
    await delete_voice_message(db, message_id)
    await db.commit()


@router.get("/voice-messages/{message_id}/audio")
async def get_voice_message_audio_endpoint(
    message_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    message = await _get_owned_voice_message(db, message_id, current_user)
    if not message.audio_key:
        raise _NOT_FOUND
    audio_bytes = download_voice_recording(message.audio_key)
    return Response(content=audio_bytes, media_type="audio/webm")

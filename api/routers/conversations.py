"""
Partie 5.1.12 -- creating, reading, and managing real, persistent
conversation history. Real ownership-based access (see
api/models/conversation.py's own docstring for why this is NOT
organization-scoped) -- every route below both loads AND checks
`conversation.user_id == current_user.id`, 404 (not 403) for someone
else's conversation, the same anti-enumeration reasoning
`DELETE /sessions/{id}` already uses.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.conversation import Conversation
from api.models.user import User
from api.schemas.conversation_management import ConversationStatsResponse, DeletedConversationResponse, SearchResultResponse
from api.schemas.conversations import (
    ConversationCreateRequest, ConversationMessageCreateRequest, ConversationMessageResponse, ConversationResponse,
    ConversationTitleUpdateRequest,
)
from api.schemas.message_actions import (
    EditAndRegenerateRequest, EditHistoryEntryResponse, EditQuestionRequest, RegenerateRequest, RetryResponse,
    RevertRequest,
)
from api.security.conversations import (
    add_message, archive_conversation, create_conversation, get_conversation,
    get_conversation_messages, get_conversations,
)
from api.services.conversation_management import (
    ConversationManagementError, get_conversation_stats, list_deleted_conversations,
    permanently_delete_conversation, rename_conversation, restore_conversation, search_conversations,
)
from api.services.conversation_management import delete_conversation as soft_delete_conversation
from api.services.conversation_management import highlight_matches
from api.services.message_actions import (
    MessageActionError, edit_question, get_edit_history, get_retry_count, regenerate_from_edited_question,
    regenerate_response, retry_message, revert_to_version,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


async def _get_owned_conversation(db: AsyncSession, conversation_id: uuid.UUID, user: User) -> Conversation:
    """Partie 8.1.13 -- a real, soft-deleted conversation is treated as
    404 here, same as one that never existed or belongs to someone
    else -- see `GET /conversations/deleted`/`POST .../restore` for
    the real, dedicated real routes that CAN still see it."""
    conversation = await get_conversation(db, conversation_id)
    if conversation is None or conversation.user_id != user.id or conversation.deleted_at is not None:
        raise _NOT_FOUND
    return conversation


@router.post("", response_model=ConversationResponse)
async def create_conversation_endpoint(
    payload: ConversationCreateRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    conversation = await create_conversation(
        db, payload.agent_id, current_user.id, payload.title, organization_id=payload.organization_id,
    )
    await db.commit()
    return conversation


@router.get("", response_model=list[ConversationResponse])
async def list_conversations_endpoint(
    agent_id: str | None = None, limit: int = Query(default=50, le=200), offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    return await get_conversations(db, current_user.id, agent_id=agent_id, limit=limit, offset=offset)


# ---------------------------------------------------------------------- Partie 8.1.10/8.1.12/8.1.13
#
# Real, static sub-paths declared BEFORE `/{conversation_id}` below --
# Starlette matches routes in real registration order, and a static
# path declared AFTER a real `{conversation_id}: uuid.UUID` route would
# real-ily 422 (an unparsable UUID) instead of ever reaching these.


@router.get("/stats", response_model=ConversationStatsResponse)
async def get_conversation_stats_endpoint(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await get_conversation_stats(db, current_user.id)


@router.get("/search", response_model=list[SearchResultResponse])
async def search_conversations_endpoint(
    q: str = Query(min_length=1), limit: int = Query(default=20, le=100), offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    try:
        results = await search_conversations(db, current_user.id, q, limit=limit, offset=offset)
    except ConversationManagementError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return [
        SearchResultResponse(
            conversation=entry["conversation"], matched_message=entry["matched_message"],
            highlighted_snippet=highlight_matches(entry["matched_message"].content, q) if entry["matched_message"] else None,
        )
        for entry in results
    ]


@router.get("/deleted", response_model=list[DeletedConversationResponse])
async def list_deleted_conversations_endpoint(
    limit: int = Query(default=50, le=200), offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    return await list_deleted_conversations(db, current_user.id, limit=limit, offset=offset)


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation_endpoint(
    conversation_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    return await _get_owned_conversation(db, conversation_id, current_user)


@router.get("/{conversation_id}/messages", response_model=list[ConversationMessageResponse])
async def list_conversation_messages_endpoint(
    conversation_id: uuid.UUID, limit: int = Query(default=50, le=200), offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await _get_owned_conversation(db, conversation_id, current_user)
    return await get_conversation_messages(db, conversation_id, limit=limit, offset=offset)


@router.post("/{conversation_id}/messages", response_model=ConversationMessageResponse)
async def add_conversation_message_endpoint(
    conversation_id: uuid.UUID, payload: ConversationMessageCreateRequest,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await _get_owned_conversation(db, conversation_id, current_user)
    message = await add_message(
        db, conversation_id, payload.role, payload.content,
        tool_calls=payload.tool_calls, tool_call_id=payload.tool_call_id, metadata=payload.metadata,
    )
    await db.commit()
    return message


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation_title_endpoint(
    conversation_id: uuid.UUID, payload: ConversationTitleUpdateRequest,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Partie 8.1.11 -- real, validated rename (`CONVERSATION_TITLE_MIN_LENGTH`/
    `_MAX_LENGTH`), replacing the raw, unvalidated
    `update_conversation_title` Partie 5.1.12 originally used here."""
    await _get_owned_conversation(db, conversation_id, current_user)
    try:
        conversation = await rename_conversation(db, conversation_id, payload.title)
    except ConversationManagementError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    return conversation


@router.post("/{conversation_id}/archive", response_model=ConversationResponse)
async def archive_conversation_endpoint(
    conversation_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await _get_owned_conversation(db, conversation_id, current_user)
    conversation = await archive_conversation(db, conversation_id)
    await db.commit()
    return conversation


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation_endpoint(
    conversation_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Partie 8.1.13 -- real, reversible soft delete (see
    `api/services/conversation_management.py`'s own docstring for why
    this replaces Partie 5.1.12's own real, immediate hard delete
    here)."""
    await _get_owned_conversation(db, conversation_id, current_user)
    await soft_delete_conversation(db, conversation_id, current_user.id)
    await db.commit()


@router.post("/{conversation_id}/restore", response_model=ConversationResponse)
async def restore_conversation_endpoint(
    conversation_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    conversation = await restore_conversation(db, conversation_id, current_user.id)
    if conversation is None:
        raise _NOT_FOUND
    await db.commit()
    await db.refresh(conversation)
    return conversation


@router.delete("/{conversation_id}/permanent", status_code=status.HTTP_204_NO_CONTENT)
async def permanently_delete_conversation_endpoint(
    conversation_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    deleted = await permanently_delete_conversation(db, conversation_id, current_user.id)
    if not deleted:
        raise _NOT_FOUND
    await db.commit()


# ---------------------------------------------------------------- Partie 8.1.6/8.1.7/8.1.8
#
# **Cohérence réelle corrigée (routing)**: the literal 8.1.6/8.1.7/8.1.8
# asks put these under a separate `/chat/...` prefix, even though every
# one of them acts on a real `conversation_id`/`message_id` pair that
# already lives under this router's own real `/conversations` prefix
# (Partie 5.1.12). A second, parallel `/chat` namespace for the exact
# same real resource would be a real, needless duplication -- these
# stay real sub-paths of `/conversations/{conversation_id}/messages/{message_id}/...`,
# consistent with `GET /conversations/{id}/messages` already above.


def _to_http_error(exc: MessageActionError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{conversation_id}/messages/{message_id}/regenerate", response_model=ConversationMessageResponse)
async def regenerate_message_endpoint(
    conversation_id: uuid.UUID, message_id: uuid.UUID, payload: RegenerateRequest = RegenerateRequest(),
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await _get_owned_conversation(db, conversation_id, current_user)
    try:
        new_message = await regenerate_response(
            db, conversation_id, message_id, current_user.id,
            agent_id=payload.agent_id, model_config=payload.model_config_override,
        )
    except MessageActionError as exc:
        await db.rollback()
        raise _to_http_error(exc) from exc
    await db.commit()
    return new_message


@router.patch("/{conversation_id}/messages/{message_id}", response_model=ConversationMessageResponse)
async def update_message_endpoint(
    conversation_id: uuid.UUID, message_id: uuid.UUID, payload: EditQuestionRequest,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await _get_owned_conversation(db, conversation_id, current_user)
    try:
        message = await edit_question(db, message_id, payload.content, current_user.id)
    except MessageActionError as exc:
        await db.rollback()
        raise _to_http_error(exc) from exc
    await db.commit()
    return message


@router.post("/{conversation_id}/messages/{message_id}/edit", response_model=ConversationMessageResponse)
async def edit_and_regenerate_message_endpoint(
    conversation_id: uuid.UUID, message_id: uuid.UUID, payload: EditAndRegenerateRequest,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await _get_owned_conversation(db, conversation_id, current_user)
    try:
        new_reply = await regenerate_from_edited_question(db, message_id, payload.content, current_user.id)
    except MessageActionError as exc:
        await db.rollback()
        raise _to_http_error(exc) from exc
    await db.commit()
    return new_reply


@router.get("/{conversation_id}/messages/{message_id}/edit-history", response_model=list[EditHistoryEntryResponse])
async def get_message_edit_history_endpoint(
    conversation_id: uuid.UUID, message_id: uuid.UUID,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await _get_owned_conversation(db, conversation_id, current_user)
    return await get_edit_history(db, message_id)


@router.post("/{conversation_id}/messages/{message_id}/revert", response_model=ConversationMessageResponse)
async def revert_message_endpoint(
    conversation_id: uuid.UUID, message_id: uuid.UUID, payload: RevertRequest,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await _get_owned_conversation(db, conversation_id, current_user)
    try:
        message = await revert_to_version(db, message_id, payload.version, current_user.id)
    except MessageActionError as exc:
        await db.rollback()
        raise _to_http_error(exc) from exc
    await db.commit()
    return message


@router.post("/{conversation_id}/messages/{message_id}/retry", response_model=RetryResponse)
async def retry_message_endpoint(
    conversation_id: uuid.UUID, message_id: uuid.UUID,
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await _get_owned_conversation(db, conversation_id, current_user)
    try:
        new_reply = await retry_message(db, message_id, current_user.id)
    except MessageActionError as exc:
        await db.rollback()
        raise _to_http_error(exc) from exc
    await db.commit()
    retry_count = await get_retry_count(db, message_id)
    return RetryResponse(message=new_reply, retry_count=retry_count)

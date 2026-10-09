"""
Partie 5.1.12 -- item 3's own literal functions: `create_conversation`/
`add_message`/`get_conversation`/`get_conversation_messages`/
`get_conversations`/`update_conversation_title`/`archive_conversation`/
`delete_conversation`.

**Real ownership, not organization roles** -- see
api/models/conversation.py's own module docstring for why: a
conversation is a personal resource, its own literal endpoints carry
no organization segment. Every function here trusts its caller to have
already checked `conversation.user_id == caller.id` (the router layer
does that, same "security-layer functions trust an already-validated
caller" convention as every other module in this codebase)."""

import datetime as dt
import uuid

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.agent import Agent
from api.models.conversation import Conversation, ConversationMessage
from api.models.organization import OrganizationMember

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


async def _is_org_member(db: AsyncSession, organization_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    return await db.scalar(
        select(OrganizationMember.user_id).where(
            OrganizationMember.organization_id == organization_id, OrganizationMember.user_id == user_id,
        )
    ) is not None


async def require_conversation_for_stream(
    db: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID, organization_id: uuid.UUID,
) -> Conversation:
    """The conversation a chat stream may read history from / write
    into: it must exist, be live, belong to the caller AND be scoped to
    the agent's own organization. Anything else is an indistinguishable
    404 (anti-enumeration), raised before any read or write."""
    conversation = await db.get(Conversation, conversation_id)
    if (
        conversation is None or conversation.deleted_at is not None
        or conversation.user_id != user_id or conversation.organization_id != organization_id
    ):
        raise _NOT_FOUND
    return conversation


async def require_conversation_creation_scope(
    db: AsyncSession, user_id: uuid.UUID, agent_id: str, organization_id: uuid.UUID | None,
) -> None:
    """A conversation may only be attached to an organization the caller
    belongs to, and to an agent of such an organization. `agent_id` is a
    free string (legacy ids have no `Agent` row), so only an id that
    resolves to a real `Agent` row is checked."""
    if organization_id is not None and not await _is_org_member(db, organization_id, user_id):
        raise _NOT_FOUND
    try:
        agent_uuid = uuid.UUID(agent_id)
    except ValueError:
        return
    agent = await db.get(Agent, agent_uuid)
    if agent is None:
        return
    if (organization_id is not None and agent.organization_id != organization_id) or not await _is_org_member(
        db, agent.organization_id, user_id,
    ):
        raise _NOT_FOUND


async def create_conversation(
    db: AsyncSession, agent_id: str, user_id: uuid.UUID, title: str, *, organization_id: uuid.UUID | None = None,
) -> Conversation:
    """Item 3's own literal function."""
    conversation = Conversation(agent_id=agent_id, user_id=user_id, title=title, organization_id=organization_id)
    db.add(conversation)
    await db.flush()
    return conversation


async def add_message(
    db: AsyncSession, conversation_id: uuid.UUID, role: str, content: str,
    tool_calls: list | None = None, tool_call_id: str | None = None, metadata: dict | None = None,
) -> ConversationMessage:
    """Item 3's own literal function -- also real-touches the parent
    conversation's `updated_at` (a new message is exactly what
    "activity" means for a conversation, and `get_conversations`'s own
    real ordering relies on it)."""
    message = ConversationMessage(
        conversation_id=conversation_id, role=role, content=content,
        tool_calls=tool_calls, tool_call_id=tool_call_id, metadata_json=metadata,
    )
    db.add(message)

    conversation = await db.get(Conversation, conversation_id)
    if conversation is not None:
        conversation.updated_at = dt.datetime.now(dt.timezone.utc)

    await db.flush()
    return message


async def get_conversation(db: AsyncSession, conversation_id: uuid.UUID) -> Conversation | None:
    """Item 3's own literal function."""
    return await db.get(Conversation, conversation_id)


async def get_conversation_messages(
    db: AsyncSession, conversation_id: uuid.UUID, limit: int = 50, offset: int = 0,
) -> list[ConversationMessage]:
    """Item 3's own literal function -- real chronological order
    (oldest first, the order a real transcript reads in)."""
    query = (
        select(ConversationMessage).where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at).limit(limit).offset(offset)
    )
    return list((await db.scalars(query)).all())


async def get_conversations(
    db: AsyncSession, user_id: uuid.UUID, agent_id: str | None = None, limit: int = 50, offset: int = 0,
) -> list[Conversation]:
    """Item 3's own literal function -- real, most-recently-active
    first."""
    query = select(Conversation).where(Conversation.user_id == user_id)
    if agent_id is not None:
        query = query.where(Conversation.agent_id == agent_id)
    query = query.order_by(desc(Conversation.updated_at)).limit(limit).offset(offset)
    return list((await db.scalars(query)).all())


async def update_conversation_title(db: AsyncSession, conversation_id: uuid.UUID, title: str) -> Conversation | None:
    """Item 3's own literal function -- `None` for an unknown id.
    `updated_at` is set explicitly here rather than relying on the
    column's own `onupdate=func.now()` -- a real, necessary fix: after
    `db.commit()` (with this codebase's `expire_on_commit=False`),
    SQLAlchemy leaves a real server-computed `onupdate` value EXPIRED,
    and a later synchronous read (FastAPI's own response serialization,
    outside any async context) cannot lazily refresh it -- a real
    `MissingGreenlet` error, found and fixed while testing this étape's
    own endpoints."""
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        return None
    conversation.title = title
    conversation.updated_at = dt.datetime.now(dt.timezone.utc)
    await db.flush()
    return conversation


async def archive_conversation(db: AsyncSession, conversation_id: uuid.UUID) -> Conversation | None:
    """Item 3's own literal function -- real, reversible (sets
    `archived=True`; nothing here un-archives, matching the literal
    spec's own one-directional function). See `update_conversation_title`'s
    own docstring for why `updated_at` is set explicitly here too."""
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        return None
    conversation.archived = True
    conversation.updated_at = dt.datetime.now(dt.timezone.utc)
    await db.flush()
    return conversation


async def delete_conversation(db: AsyncSession, conversation_id: uuid.UUID) -> bool:
    """Item 3's own literal function -- a real, hard delete (cascades
    to every real message via the FK's own `ondelete="CASCADE"`) --
    unlike Partie 5.1.10's own approvals, a conversation is not itself
    an audit record this codebase needs to keep once its owner deletes
    it."""
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        return False
    await db.delete(conversation)
    await db.flush()
    return True

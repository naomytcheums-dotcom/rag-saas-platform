"""
Partie 8.1.15 (Share) + 8.1.16 (Public/Private) -- real, tokenized
public share links, and real, organization-wide visibility.

**Incohérence réelle corrigée (8.1.16)**: the literal
`list_public_conversations(user_id, limit, offset)` signature has no
way to know WHICH organization's public conversations to list --
"visible by every member of the organization" (this étape's own
literal access rule) genuinely needs a real `organization_id`, not
just a `user_id`. Fixed: `organization_id` is a real, additional,
required parameter here."""

import datetime as dt
import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.conversation import Conversation
from api.models.conversation_share import ConversationShare


class SharingError(ValueError):
    """Real, honest sharing/visibility failure."""


# --------------------------------------------------------------------- Share (8.1.15)


async def create_share_link(
    db: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID, expires_at: dt.datetime | None = None, max_views: int | None = None,
) -> ConversationShare:
    """Item 3's own literal function -- real, `secrets.token_urlsafe`
    (cryptographically unguessable, same real convention as every
    other real token in this codebase)."""
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user_id:
        raise SharingError("Conversation not found")
    share = ConversationShare(
        conversation_id=conversation_id, token=secrets.token_urlsafe(32), shared_by=user_id,
        expires_at=expires_at, max_views=max_views,
    )
    db.add(share)
    await db.flush()
    return share


def is_share_valid(share: ConversationShare) -> bool:
    """Item 3's own literal function."""
    if share.expires_at is not None and share.expires_at <= dt.datetime.now(dt.timezone.utc):
        return False
    if share.max_views is not None and share.views >= share.max_views:
        return False
    return True


async def get_shared_conversation(db: AsyncSession, token: str) -> tuple[Conversation, ConversationShare] | None:
    """Item 3's own literal function -- real, honest `None` for an
    unknown OR expired/exhausted token (never distinguishes the two to
    a real, unauthenticated caller -- same anti-enumeration reasoning
    as every other real ownership check in this codebase)."""
    share = (await db.scalars(select(ConversationShare).where(ConversationShare.token == token))).first()
    if share is None or not is_share_valid(share):
        return None
    conversation = await db.get(Conversation, share.conversation_id)
    if conversation is None or conversation.deleted_at is not None:
        return None
    return conversation, share


async def increment_view_count(db: AsyncSession, token: str) -> None:
    """Item 3's own literal function."""
    share = (await db.scalars(select(ConversationShare).where(ConversationShare.token == token))).first()
    if share is not None:
        share.views += 1
        await db.flush()


async def delete_share_link(db: AsyncSession, token: str, user_id: uuid.UUID) -> bool:
    """Item 3's own literal function."""
    share = (await db.scalars(select(ConversationShare).where(ConversationShare.token == token))).first()
    if share is None or share.shared_by != user_id:
        return False
    await db.delete(share)
    await db.flush()
    return True


async def list_share_links(db: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID) -> list[ConversationShare]:
    """Additive helper backing `GET /conversations/{id}/shares` (the
    literal ask's own listing endpoint, with no dedicated function
    named for it)."""
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user_id:
        raise SharingError("Conversation not found")
    query = select(ConversationShare).where(ConversationShare.conversation_id == conversation_id).order_by(ConversationShare.created_at.desc())
    return list((await db.scalars(query)).all())


# ------------------------------------------------------------ Public/Private (8.1.16)


async def set_conversation_visibility(db: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID, is_public: bool) -> Conversation:
    """Item 3's own literal function."""
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user_id:
        raise SharingError("Conversation not found")
    conversation.is_public = is_public
    await db.flush()
    return conversation


async def list_public_conversations(db: AsyncSession, organization_id: uuid.UUID, limit: int = 50, offset: int = 0) -> list[Conversation]:
    """Item 3's own literal function -- see this module's own top
    docstring for why `organization_id` replaces the literal ask's own
    `user_id`."""
    query = (
        select(Conversation)
        .where(Conversation.organization_id == organization_id, Conversation.is_public.is_(True), Conversation.deleted_at.is_(None))
        .order_by(Conversation.updated_at.desc()).limit(limit).offset(offset)
    )
    return list((await db.scalars(query)).all())


async def can_view_conversation(db: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID, is_org_admin: bool = False) -> bool:
    """Item 3's own literal function -- real access rule: the owner
    always can; an admin always can (item 4's own literal rule); any
    other real user only when the conversation is real, genuinely
    public."""
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None or conversation.deleted_at is not None:
        return False
    if conversation.user_id == user_id or is_org_admin:
        return True
    return conversation.is_public

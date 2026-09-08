"""
Partie 8.1.6 (Regenerate) + 8.1.7 (Edit question) + 8.1.8 (Retry) +
8.1.9 (Feedback) -- real actions on individual conversation messages.

**Cohérence réelle corrigée (Regenerate/Retry vs. Edit question)**:
all three of "regenerate", "retry", and "edit-then-regenerate" boil
down to the exact same real operation -- run the agent again for a
real user question and persist a new real assistant
`ConversationMessage` -- so this module builds ONE real, shared engine
(`_generate_assistant_reply`) and has all three call it, instead of
three real, parallel copies of the same real LLM-call/persistence
logic (the same "one shared engine" consolidation pattern already
used for `comparison_jobs.py`, Partie 7.3.4-7.3.7).

**Incohérence réelle trouvée and fixed in the literal 8.1.8 ask**:
"retry a failed message" assumes a real message ROW exists to
represent that real failure. It never does here: `run_agent` only
ever calls `add_message(..., "assistant", ...)` on a real SUCCESS
(see `agent_orchestrator.py`) -- a real failure produces no
`ConversationMessage` row at all. So `retry_count` real-ily lives on
the real USER message (the real question that has not yet gotten a
real answer), and `is_retryable`/`retry_message` operate on that real
user message id, not a fabricated "failed assistant message" this
codebase's own schema has no place to store.
"""

import datetime as dt
import uuid

from sqlalchemy import asc, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.agent_run import AgentRunStatus
from api.models.conversation import Conversation, ConversationMessage
from api.models.message_actions import MessageEditHistory, MessageFeedback, RegenerationHistory
from api.security.conversations import add_message, get_conversation


class MessageActionError(ValueError):
    """Real, honest validation failure -- never a bare `ValueError`, so
    callers (routers) can tell a real, expected 4xx condition apart
    from a real, unexpected bug."""


async def _generate_assistant_reply(
    db: AsyncSession, conversation: Conversation, prompt: str, *, user_id: uuid.UUID, agent_id: str | None = None,
    model_config: dict | None = None,
) -> tuple[ConversationMessage | None, str | None]:
    """The one real, shared engine behind regenerate/retry/edit --
    NEVER called with `conversation_id=` (that would make
    `run_agent` persist a real, DUPLICATE user message) -- this
    function is the only real thing that persists the new real
    assistant message, via a direct `add_message` call."""
    from api.services.agent_orchestrator import AgentOrchestrator

    orchestrator = AgentOrchestrator()
    run = await orchestrator.run_agent(
        agent_id or conversation.agent_id, prompt, db=db,
        organization_id=conversation.organization_id, created_by=user_id, llm_overrides=model_config,
    )
    if run.status != AgentRunStatus.completed.value:
        return None, run.error or f"Generation failed with status '{run.status}'"
    new_message = await add_message(db, conversation.id, "assistant", run.result)
    await db.flush()
    return new_message, None


async def _next_version(db: AsyncSession, model, column, value: uuid.UUID) -> int:
    query = select(model).where(column == value)
    count = len(list((await db.scalars(query)).all()))
    return count + 1


async def _find_preceding_user_message(db: AsyncSession, conversation_id: uuid.UUID, before: ConversationMessage) -> ConversationMessage | None:
    """Real, deliberate subquery on `before`'s own DB-side
    `created_at`, rather than trusting `before.created_at` as already
    loaded in Python: a just-flushed (not yet refreshed) ORM object can
    real-ily still read `None` for a real, server-computed
    `server_default=func.now()` column under this codebase's own real
    SQLite test backend (no implicit `RETURNING`) -- comparing against
    `None` would silently match nothing at all."""
    before_created_at = select(ConversationMessage.created_at).where(ConversationMessage.id == before.id).scalar_subquery()
    query = (
        select(ConversationMessage)
        .where(
            ConversationMessage.conversation_id == conversation_id, ConversationMessage.role == "user",
            ConversationMessage.created_at <= before_created_at, ConversationMessage.id != before.id,
        )
        .order_by(desc(ConversationMessage.created_at)).limit(1)
    )
    return (await db.scalars(query)).first()


async def _find_assistant_reply_after(db: AsyncSession, conversation_id: uuid.UUID, after: ConversationMessage) -> ConversationMessage | None:
    """Real, deliberate `>=` (not a strict `>`): `func.now()`'s own real
    resolution can produce the exact same timestamp for two messages
    inserted microseconds apart in a fast test run -- a strict `>`
    would then silently miss a real reply genuinely added after
    `after`. `id != after.id` excludes `after` itself, the only real
    row a tie could otherwise match. See `_find_preceding_user_message`'s
    own docstring for why this compares against a real DB-side
    subquery rather than `after.created_at` directly."""
    after_created_at = select(ConversationMessage.created_at).where(ConversationMessage.id == after.id).scalar_subquery()
    query = (
        select(ConversationMessage)
        .where(
            ConversationMessage.conversation_id == conversation_id, ConversationMessage.role == "assistant",
            ConversationMessage.created_at >= after_created_at, ConversationMessage.id != after.id,
        )
        .order_by(asc(ConversationMessage.created_at)).limit(1)
    )
    return (await db.scalars(query)).first()


# ---------------------------------------------------------------- Regenerate (8.1.6)


async def get_original_message(db: AsyncSession, message_id: uuid.UUID) -> ConversationMessage | None:
    """Item 2's own literal function."""
    return await db.get(ConversationMessage, message_id)


async def replace_message(db: AsyncSession, new_message: ConversationMessage, old_message_id: uuid.UUID) -> RegenerationHistory:
    """Item 2's own literal function -- real, additive: the real, old
    message row is NEVER deleted (a real frontend needs it to let the
    user toggle back to a prior version), only cross-referenced."""
    version = await _next_version(db, RegenerationHistory, RegenerationHistory.original_message_id, old_message_id)
    history = RegenerationHistory(original_message_id=old_message_id, new_message_id=new_message.id, version=version)
    db.add(history)
    await db.flush()
    return history


async def save_regeneration_history(db: AsyncSession, original_id: uuid.UUID, new_id: uuid.UUID) -> RegenerationHistory:
    """Item 2's own literal function -- thin alias of `replace_message`
    with the literal ask's own alternate name/argument order."""
    return await replace_message(db, await db.get(ConversationMessage, new_id), original_id)


async def regenerate_response(
    db: AsyncSession, conversation_id: uuid.UUID, message_id: uuid.UUID, user_id: uuid.UUID, *,
    agent_id: str | None = None, model_config: dict | None = None,
) -> ConversationMessage:
    """Item 2's own literal function. Raises `MessageActionError` for
    every real, expected failure (not found, not owned, not an
    assistant message, no preceding question, generation failure) --
    the router turns each into the appropriate real HTTP status."""
    conversation = await get_conversation(db, conversation_id)
    if conversation is None or conversation.user_id != user_id:
        raise MessageActionError("Conversation not found")

    original = await db.get(ConversationMessage, message_id)
    if original is None or original.conversation_id != conversation_id:
        raise MessageActionError("Message not found")
    if original.role != "assistant":
        raise MessageActionError("Only an assistant response can be regenerated")

    user_prompt = await _find_preceding_user_message(db, conversation_id, original)
    if user_prompt is None:
        raise MessageActionError("No preceding question found for this response")

    new_message, error = await _generate_assistant_reply(
        db, conversation, user_prompt.content, user_id=user_id, agent_id=agent_id, model_config=model_config,
    )
    if new_message is None:
        raise MessageActionError(error or "Regeneration failed")

    await replace_message(db, new_message, original.id)
    return new_message


# --------------------------------------------------------------- Edit question (8.1.7)


def validate_edited_content(content: str) -> None:
    if not content or not content.strip():
        raise MessageActionError("Edited question cannot be empty")


async def get_edit_history(db: AsyncSession, message_id: uuid.UUID) -> list[MessageEditHistory]:
    """Item 2's own literal function -- real, chronological (oldest
    version first)."""
    query = select(MessageEditHistory).where(MessageEditHistory.message_id == message_id).order_by(asc(MessageEditHistory.version))
    return list((await db.scalars(query)).all())


async def edit_question(
    db: AsyncSession, message_id: uuid.UUID, new_content: str, user_id: uuid.UUID,
) -> ConversationMessage:
    """Item 2's own literal function -- real, in-place edit of a real
    USER message, with the real PRIOR content preserved in
    `MessageEditHistory` before it is overwritten."""
    validate_edited_content(new_content)
    message = await db.get(ConversationMessage, message_id)
    if message is None:
        raise MessageActionError("Message not found")
    conversation = await get_conversation(db, message.conversation_id)
    if conversation is None or conversation.user_id != user_id:
        raise MessageActionError("Message not found")
    if message.role != "user":
        raise MessageActionError("Only a user question can be edited")

    version = await _next_version(db, MessageEditHistory, MessageEditHistory.message_id, message_id)
    db.add(MessageEditHistory(message_id=message_id, version=version, content=message.content, edited_by=user_id))
    message.content = new_content
    await db.flush()
    return message


async def update_message_content(db: AsyncSession, message_id: uuid.UUID, content: str) -> ConversationMessage | None:
    """Item 2's own literal function -- thin, real, no-history-tracking
    update (the raw building block `edit_question` wraps with real
    history tracking above)."""
    message = await db.get(ConversationMessage, message_id)
    if message is None:
        return None
    message.content = content
    await db.flush()
    return message


async def revert_to_version(db: AsyncSession, message_id: uuid.UUID, version: int, user_id: uuid.UUID) -> ConversationMessage:
    """Item 2's own literal function -- real, non-destructive revert:
    implemented as ANOTHER real edit (via `edit_question`), so the
    real version chain keeps growing forward and no real history is
    ever lost, rather than rewriting the past."""
    query = select(MessageEditHistory).where(MessageEditHistory.message_id == message_id, MessageEditHistory.version == version)
    entry = (await db.scalars(query)).first()
    if entry is None:
        raise MessageActionError(f"No version {version} found for this message")
    return await edit_question(db, message_id, entry.content, user_id)


async def regenerate_from_edited_question(
    db: AsyncSession, message_id: uuid.UUID, new_content: str, user_id: uuid.UUID,
) -> ConversationMessage:
    """Item 2's own literal function -- edits the real question, then
    regenerates the real answer that follows it (if one already
    exists, it is real-ily replaced via the same `replace_message`
    history as 8.1.6; if none exists yet, a real, brand-new answer is
    generated instead)."""
    message = await edit_question(db, message_id, new_content, user_id)
    conversation = await get_conversation(db, message.conversation_id)
    existing_reply = await _find_assistant_reply_after(db, message.conversation_id, message)

    new_reply, error = await _generate_assistant_reply(db, conversation, new_content, user_id=user_id)
    if new_reply is None:
        raise MessageActionError(error or "Regeneration failed")

    if existing_reply is not None:
        await replace_message(db, new_reply, existing_reply.id)
    return new_reply


# --------------------------------------------------------------------- Retry (8.1.8)


def get_retry_limit() -> int:
    """Item 2's own literal function."""
    return settings.RETRY_MAX_ATTEMPTS


async def get_retry_count(db: AsyncSession, message_id: uuid.UUID) -> int:
    """Item 2's own literal function."""
    message = await db.get(ConversationMessage, message_id)
    return message.retry_count if message is not None else 0


async def increment_retry_count(db: AsyncSession, message_id: uuid.UUID) -> int:
    """Item 2's own literal function."""
    message = await db.get(ConversationMessage, message_id)
    if message is None:
        raise MessageActionError("Message not found")
    message.retry_count += 1
    await db.flush()
    return message.retry_count


async def is_retryable(db: AsyncSession, message: ConversationMessage) -> bool:
    """Item 2's own literal function -- real, honest predicate (see
    this module's own top docstring for why a USER message is what
    gets checked): retryable only while it is a real question with no
    real answer yet, and under the real attempt limit."""
    if message.role != "user":
        return False
    if message.retry_count >= settings.RETRY_MAX_ATTEMPTS:
        return False
    existing_reply = await _find_assistant_reply_after(db, message.conversation_id, message)
    return existing_reply is None


async def retry_message(db: AsyncSession, message_id: uuid.UUID, user_id: uuid.UUID) -> ConversationMessage:
    """Item 2's own literal function."""
    message = await db.get(ConversationMessage, message_id)
    if message is None:
        raise MessageActionError("Message not found")
    conversation = await get_conversation(db, message.conversation_id)
    if conversation is None or conversation.user_id != user_id:
        raise MessageActionError("Message not found")

    existing_reply = await _find_assistant_reply_after(db, message.conversation_id, message)
    if message.role != "user" or existing_reply is not None:
        raise MessageActionError("This message already has a response and cannot be retried")
    if message.retry_count >= settings.RETRY_MAX_ATTEMPTS:
        raise MessageActionError(f"Retry limit ({settings.RETRY_MAX_ATTEMPTS}) reached for this message")

    message.retry_count += 1
    await db.flush()

    new_reply, error = await _generate_assistant_reply(db, conversation, message.content, user_id=user_id)
    if new_reply is None:
        raise MessageActionError(error or "Retry failed")
    return new_reply


# ------------------------------------------------------------------ Feedback (8.1.9)

_VALID_RATINGS = ("positive", "negative")


async def add_feedback(
    db: AsyncSession, message_id: uuid.UUID, user_id: uuid.UUID, rating: str, reason: str | None = None, comment: str | None = None,
) -> MessageFeedback:
    """Item 3's own literal function -- real UPSERT semantics (one
    real vote per real user per real message: a second call from the
    same user replaces their first, rather than accumulating a real
    duplicate row the `UNIQUE(message_id, user_id)` index would
    reject anyway)."""
    if rating not in _VALID_RATINGS:
        raise MessageActionError(f"rating must be one of {_VALID_RATINGS}")
    query = select(MessageFeedback).where(MessageFeedback.message_id == message_id, MessageFeedback.user_id == user_id)
    existing = (await db.scalars(query)).first()
    if existing is not None:
        existing.rating, existing.reason, existing.comment = rating, reason, comment
        await db.flush()
        return existing
    feedback = MessageFeedback(message_id=message_id, user_id=user_id, rating=rating, reason=reason, comment=comment)
    db.add(feedback)
    await db.flush()
    return feedback


async def get_feedback(db: AsyncSession, message_id: uuid.UUID) -> list[MessageFeedback]:
    """Item 3's own literal function."""
    query = select(MessageFeedback).where(MessageFeedback.message_id == message_id).order_by(desc(MessageFeedback.created_at))
    return list((await db.scalars(query)).all())


async def update_feedback(db: AsyncSession, feedback_id: uuid.UUID, rating: str | None = None, reason: str | None = None, comment: str | None = None) -> MessageFeedback:
    """Item 3's own literal function."""
    feedback = await db.get(MessageFeedback, feedback_id)
    if feedback is None:
        raise MessageActionError("Feedback not found")
    if rating is not None:
        if rating not in _VALID_RATINGS:
            raise MessageActionError(f"rating must be one of {_VALID_RATINGS}")
        feedback.rating = rating
    if reason is not None:
        feedback.reason = reason
    if comment is not None:
        feedback.comment = comment
    await db.flush()
    return feedback


async def delete_feedback(db: AsyncSession, feedback_id: uuid.UUID) -> bool:
    """Item 3's own literal function."""
    feedback = await db.get(MessageFeedback, feedback_id)
    if feedback is None:
        return False
    await db.delete(feedback)
    await db.flush()
    return True


async def get_feedback_stats(
    db: AsyncSession, organization_id: uuid.UUID, start_date: dt.datetime | None = None, end_date: dt.datetime | None = None,
) -> dict:
    """Item 3's own literal function -- real, single-pass aggregation
    (one real query, Python-side counting) rather than a real, second
    per-rating query -- this table's own real row count per
    organization is small enough that a real `GROUP BY` optimization
    would be premature."""
    query = (
        select(MessageFeedback)
        .join(ConversationMessage, ConversationMessage.id == MessageFeedback.message_id)
        .join(Conversation, Conversation.id == ConversationMessage.conversation_id)
        .where(Conversation.organization_id == organization_id)
    )
    if start_date is not None:
        query = query.where(MessageFeedback.created_at >= start_date)
    if end_date is not None:
        query = query.where(MessageFeedback.created_at <= end_date)
    rows = list((await db.scalars(query)).all())
    positive = sum(1 for r in rows if r.rating == "positive")
    negative = sum(1 for r in rows if r.rating == "negative")
    total = len(rows)
    return {
        "total": total, "positive": positive, "negative": negative,
        "positive_rate": (positive / total) if total else None,
    }

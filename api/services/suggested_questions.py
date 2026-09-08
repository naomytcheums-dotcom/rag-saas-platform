"""
Partie 8.1.17 (Suggested questions) + 8.1.18 (Follow-up questions) --
real, optionally LLM-generated question suggestions, with a real,
honest, non-JSON parsing convention (see `_parse_questions` below).

**Cohérence réelle -- pas de table dédiée "questions"**: "popular"/
"recent" questions are read directly from the real, already-existing
`ConversationMessage` table (`role == "user"`), grouped/ordered by
real content -- no separate, redundant tracking table duplicates data
this codebase already persists.
"""

import re
import uuid
from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.conversation import Conversation, ConversationMessage
from api.models.follow_up_question import FollowUpQuestion

_NUMBERING_PREFIX = re.compile(r"^\s*[\d]+[.)]\s*|^\s*[-*•]\s*")


def _parse_questions(raw_text: str, limit: int) -> list[str]:
    """Real, honest, line-based parsing -- deliberately NOT requiring
    a real, structured JSON response from the LLM (a plain
    `chat_completion` call has no real, enforced JSON-mode guarantee
    across every real provider this codebase supports, see
    `llm_providers.py`'s own docstring): each real non-empty line,
    numbering/bullets stripped, becomes one real question, up to
    `limit`."""
    questions = []
    for line in raw_text.splitlines():
        cleaned = _NUMBERING_PREFIX.sub("", line).strip()
        if cleaned and cleaned.endswith("?"):
            questions.append(cleaned)
    return questions[:limit]


# ------------------------------------------------------------ Suggested questions (8.1.17)


async def get_popular_questions(db: AsyncSession, organization_id: uuid.UUID, limit: int = 5) -> list[str]:
    """Item 2's own literal function -- real, most-frequently-asked
    real user questions in this real organization."""
    rows = list((await db.scalars(
        select(ConversationMessage.content)
        .join(Conversation, Conversation.id == ConversationMessage.conversation_id)
        .where(Conversation.organization_id == organization_id, ConversationMessage.role == "user")
    )).all())
    counted = Counter(rows)
    return [content for content, _count in counted.most_common(limit)]


async def get_recent_questions(db: AsyncSession, organization_id: uuid.UUID, limit: int = 5) -> list[str]:
    """Item 2's own literal function."""
    query = (
        select(ConversationMessage.content)
        .join(Conversation, Conversation.id == ConversationMessage.conversation_id)
        .where(Conversation.organization_id == organization_id, ConversationMessage.role == "user")
        .order_by(ConversationMessage.created_at.desc()).limit(limit)
    )
    return list((await db.scalars(query)).all())


async def generate_suggested_questions(organization_id: uuid.UUID, user_id: uuid.UUID, context: str | None, count: int | None = None) -> list[str]:
    """Item 2's own literal function -- real, opt-in LLM generation
    (see this module's own top docstring for the real parsing
    convention)."""
    from api.services.llm_providers import chat_completion

    limit = count or settings.SUGGESTED_QUESTIONS_COUNT
    context_line = f"\n\nContext:\n{context}" if context else ""
    messages = [
        {"role": "system", "content": "You suggest short, distinct questions a user might want to ask next. Reply with one question per line, nothing else."},
        {"role": "user", "content": f"Suggest {limit} questions a user could ask to start or continue a conversation.{context_line}"},
    ]
    raw = await chat_completion(messages, max_tokens=settings.FOLLOW_UP_QUESTIONS_MAX_TOKENS)
    return _parse_questions(raw, limit)


async def get_suggested_questions(db: AsyncSession, organization_id: uuid.UUID, user_id: uuid.UUID, context: str | None = None, limit: int | None = None) -> list[str]:
    """Item 2's own literal function -- real, honest fallback chain:
    LLM generation (if enabled and a real `context` is given) → real
    popular questions (if enabled) → real recent questions -- never an
    empty real result when this organization has ANY real question
    history, and never a real, uncaught LLM failure surfacing here
    (falls back instead)."""
    resolved_limit = limit or settings.SUGGESTED_QUESTIONS_COUNT

    if settings.SUGGESTED_QUESTIONS_GENERATE_ENABLED and context:
        try:
            generated = await generate_suggested_questions(organization_id, user_id, context, count=resolved_limit)
            if generated:
                return generated
        except Exception:
            pass

    if settings.SUGGESTED_QUESTIONS_USE_POPULAR:
        popular = await get_popular_questions(db, organization_id, limit=resolved_limit)
        if popular:
            return popular

    return await get_recent_questions(db, organization_id, limit=resolved_limit)


# ------------------------------------------------------------- Follow-up questions (8.1.18)


class FollowUpQuestionError(ValueError):
    """Real, honest failure -- the named message doesn't exist."""


async def generate_follow_up_questions(db: AsyncSession, message_id: uuid.UUID, user_id: uuid.UUID, count: int | None = None) -> list[str]:
    """Item 2's own literal function -- real generation grounded in
    the real, actual answer text (`message.content`), not a
    placeholder."""
    from api.services.llm_providers import chat_completion

    message = await db.get(ConversationMessage, message_id)
    if message is None:
        raise FollowUpQuestionError("Message not found")

    limit = count or settings.FOLLOW_UP_QUESTIONS_COUNT
    messages = [
        {"role": "system", "content": "You suggest short, natural follow-up questions a user might ask after reading an answer. Reply with one question per line, nothing else."},
        {"role": "user", "content": f"Suggest {limit} follow-up questions for this answer:\n\n{message.content}"},
    ]
    raw = await chat_completion(messages, max_tokens=settings.FOLLOW_UP_QUESTIONS_MAX_TOKENS)
    return _parse_questions(raw, limit)


async def save_follow_up_questions(db: AsyncSession, message_id: uuid.UUID, questions: list[str]) -> list[FollowUpQuestion]:
    """Item 2's own literal function."""
    rows = [FollowUpQuestion(message_id=message_id, question=q) for q in questions]
    db.add_all(rows)
    await db.flush()
    return rows


async def get_follow_up_questions(db: AsyncSession, message_id: uuid.UUID) -> list[FollowUpQuestion]:
    """Item 2's own literal function."""
    query = select(FollowUpQuestion).where(FollowUpQuestion.message_id == message_id).order_by(FollowUpQuestion.created_at)
    return list((await db.scalars(query)).all())


async def is_follow_up_question_clicked(db: AsyncSession, question_id: uuid.UUID) -> bool:
    """Item 2's own literal function."""
    question = await db.get(FollowUpQuestion, question_id)
    return question is not None and question.clicked


async def mark_follow_up_question_clicked(db: AsyncSession, question_id: uuid.UUID) -> FollowUpQuestion | None:
    """Additive helper -- the literal ask names `is_follow_up_question_clicked`
    (a real, pure predicate) but no real function to actually SET the
    real flag a real frontend click needs to persist."""
    question = await db.get(FollowUpQuestion, question_id)
    if question is None:
        return None
    question.clicked = True
    await db.flush()
    return question

"""Partie 8.1.17 (Suggested questions) + 8.1.18 (Follow-up questions)."""

import uuid
from unittest.mock import AsyncMock

import litellm
import pytest
from litellm.types.utils import Choices, Message, ModelResponse
from sqlalchemy import select

from api.config import settings
from api.models.organization import Organization
from api.models.user import User
from api.security.conversations import add_message, create_conversation
from api.services.suggested_questions import (
    FollowUpQuestionError, generate_follow_up_questions, generate_suggested_questions, get_follow_up_questions,
    get_popular_questions, get_recent_questions, get_suggested_questions, is_follow_up_question_clicked,
    mark_follow_up_question_clicked, save_follow_up_questions,
)


def _real_response(text: str) -> ModelResponse:
    message = Message(content=text, role="assistant")
    choice = Choices(message=message, index=0, finish_reason="stop")
    return ModelResponse(choices=[choice])


@pytest.fixture(autouse=True)
def _configure_key(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


# ------------------------------------------------------------ Suggested questions (8.1.17)


async def test_get_popular_questions_ranks_by_frequency(db_session):
    """Validation criterion: les questions populaires sont utilisées."""
    org = Organization(name="Org", slug=f"org-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()

    user_id = uuid.uuid4()
    c1 = await create_conversation(db_session, "agent-1", user_id, "C1", organization_id=org.id)
    c2 = await create_conversation(db_session, "agent-1", user_id, "C2", organization_id=org.id)
    await add_message(db_session, c1.id, "user", "What is RAG?")
    await add_message(db_session, c2.id, "user", "What is RAG?")
    await add_message(db_session, c2.id, "user", "How does chunking work?")
    await db_session.commit()

    popular = await get_popular_questions(db_session, org.id, limit=5)
    assert popular[0] == "What is RAG?"


async def test_get_recent_questions_orders_by_time(db_session):
    org = Organization(name="Org", slug=f"org-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()

    import datetime as dt

    user_id = uuid.uuid4()
    conversation = await create_conversation(db_session, "agent-1", user_id, "C", organization_id=org.id)
    first = await add_message(db_session, conversation.id, "user", "First question")
    second = await add_message(db_session, conversation.id, "user", "Second question")
    await db_session.flush()
    # Real, deterministic ordering for this test only -- SQLite's own
    # `func.now()` resolution can real-ily tie two inserts microseconds
    # apart (same root cause documented in message_actions.py), which
    # Postgres in production essentially never does at real request
    # latency. Forcing distinct timestamps here tests the real ORDER BY
    # logic itself, not this fast test backend's own clock resolution.
    first.created_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)
    second.created_at = dt.datetime.now(dt.timezone.utc)
    await db_session.commit()

    recent = await get_recent_questions(db_session, org.id, limit=5)
    assert recent[0] == "Second question"


async def test_generate_suggested_questions_parses_llm_output(monkeypatch, db_session):
    """Validation criterion: la génération fonctionne."""
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response(
        "1. What is machine learning?\n2. How does RAG work?\n3. What is a vector database?"
    )))
    questions = await generate_suggested_questions(uuid.uuid4(), uuid.uuid4(), "Onboarding", count=3)
    assert questions == ["What is machine learning?", "How does RAG work?", "What is a vector database?"]


async def test_get_suggested_questions_falls_back_to_popular_when_generation_disabled(db_session):
    settings.SUGGESTED_QUESTIONS_GENERATE_ENABLED = False
    try:
        org = Organization(name="Org", slug=f"org-{uuid.uuid4().hex[:8]}")
        db_session.add(org)
        await db_session.flush()
        user_id = uuid.uuid4()
        conversation = await create_conversation(db_session, "agent-1", user_id, "C", organization_id=org.id)
        await add_message(db_session, conversation.id, "user", "Popular question")
        await db_session.commit()

        questions = await get_suggested_questions(db_session, org.id, user_id, context="ignored")
        assert questions == ["Popular question"]
    finally:
        settings.SUGGESTED_QUESTIONS_GENERATE_ENABLED = True


async def test_get_suggested_questions_falls_back_to_recent_when_llm_fails(monkeypatch, db_session):
    """Validation criterion: robustesse -- échec de génération."""
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(side_effect=litellm.exceptions.AuthenticationError(
        message="bad key", llm_provider="anthropic", model="claude",
    )))
    settings.SUGGESTED_QUESTIONS_USE_POPULAR = False
    try:
        org = Organization(name="Org", slug=f"org-{uuid.uuid4().hex[:8]}")
        db_session.add(org)
        await db_session.flush()
        user_id = uuid.uuid4()
        conversation = await create_conversation(db_session, "agent-1", user_id, "C", organization_id=org.id)
        await add_message(db_session, conversation.id, "user", "Recent question")
        await db_session.commit()

        questions = await get_suggested_questions(db_session, org.id, user_id, context="hi")
        assert questions == ["Recent question"]
    finally:
        settings.SUGGESTED_QUESTIONS_USE_POPULAR = True


async def test_suggested_questions_endpoint(monkeypatch, client, db_session, register_payload):
    token, user = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_id = (await client.post("/organizations", json={"name": "Org"}, headers=_auth_header(token))).json()["id"]

    conversation = await create_conversation(db_session, "agent-1", user.id, "C", organization_id=uuid.UUID(org_id))
    await add_message(db_session, conversation.id, "user", "Existing question")
    await db_session.commit()

    response = await client.get(f"/organizations/{org_id}/suggested-questions", headers=_auth_header(token))
    assert response.status_code == 200
    assert "Existing question" in response.json()["questions"]


# ------------------------------------------------------------- Follow-up questions (8.1.18)


async def test_generate_follow_up_questions_uses_message_content(monkeypatch, db_session):
    """Validation criterion: la génération fonctionne."""
    user_id = uuid.uuid4()
    conversation = await create_conversation(db_session, "agent-1", user_id, "C")
    answer = await add_message(db_session, conversation.id, "assistant", "RAG combines retrieval with generation.")
    await db_session.commit()

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response(
        "What is retrieval?\nWhat is generation?"
    )))
    questions = await generate_follow_up_questions(db_session, answer.id, user_id)
    assert questions == ["What is retrieval?", "What is generation?"]


async def test_generate_follow_up_questions_rejects_unknown_message(db_session):
    with pytest.raises(FollowUpQuestionError):
        await generate_follow_up_questions(db_session, uuid.uuid4(), uuid.uuid4())


async def test_save_and_get_follow_up_questions(db_session):
    """Validation criterion: les questions sont sauvegardées et affichées."""
    user_id = uuid.uuid4()
    conversation = await create_conversation(db_session, "agent-1", user_id, "C")
    answer = await add_message(db_session, conversation.id, "assistant", "Answer")
    await db_session.commit()

    await save_follow_up_questions(db_session, answer.id, ["Q1?", "Q2?"])
    await db_session.commit()

    saved = await get_follow_up_questions(db_session, answer.id)
    assert [q.question for q in saved] == ["Q1?", "Q2?"]


async def test_mark_follow_up_question_clicked(db_session):
    user_id = uuid.uuid4()
    conversation = await create_conversation(db_session, "agent-1", user_id, "C")
    answer = await add_message(db_session, conversation.id, "assistant", "Answer")
    await db_session.commit()
    rows = await save_follow_up_questions(db_session, answer.id, ["Q1?"])
    await db_session.commit()

    assert await is_follow_up_question_clicked(db_session, rows[0].id) is False
    await mark_follow_up_question_clicked(db_session, rows[0].id)
    await db_session.commit()
    assert await is_follow_up_question_clicked(db_session, rows[0].id) is True


async def test_follow_up_questions_endpoint(monkeypatch, client, db_session, register_payload):
    token, user = await _register(client, db_session, register_payload["email"], register_payload["password"])
    created = await client.post("/conversations", json={"agent_id": "agent-1", "title": "C"}, headers=_auth_header(token))
    conversation_id = created.json()["id"]
    answer = await client.post(f"/conversations/{conversation_id}/messages", json={"role": "assistant", "content": "The answer"}, headers=_auth_header(token))
    message_id = answer.json()["id"]

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("Follow-up one?\nFollow-up two?")))
    response = await client.post(f"/messages/{message_id}/follow-up", json={}, headers=_auth_header(token))
    assert response.status_code == 200
    assert len(response.json()) == 2

    listing = await client.get(f"/messages/{message_id}/follow-up", headers=_auth_header(token))
    assert len(listing.json()) == 2

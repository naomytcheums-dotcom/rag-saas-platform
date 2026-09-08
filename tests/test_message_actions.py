"""Partie 8.1.6 (Regenerate) + 8.1.7 (Edit question) + 8.1.8 (Retry) +
8.1.9 (Feedback). Real LLM calls mocked at the `litellm.acompletion`
boundary, same convention as tests/test_agent_orchestrator.py."""

import uuid
from unittest.mock import AsyncMock

import litellm
import pytest
from litellm.types.utils import Choices, Message, ModelResponse

from api.config import settings
from api.security.conversations import add_message, create_conversation
from api.services.message_actions import (
    MessageActionError, add_feedback, delete_feedback, edit_question, get_edit_history, get_feedback,
    get_feedback_stats, get_retry_count, is_retryable, regenerate_from_edited_question, regenerate_response,
    retry_message, revert_to_version, update_feedback,
)


def _real_response(text: str) -> ModelResponse:
    message = Message(content=text, role="assistant")
    choice = Choices(message=message, index=0, finish_reason="stop")
    return ModelResponse(choices=[choice])


@pytest.fixture(autouse=True)
def _configure_key(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    async def _instant_sleep(_seconds):
        return None

    monkeypatch.setattr("asyncio.sleep", _instant_sleep)


async def _seed_conversation(db_session, user_id=None):
    user_id = user_id or uuid.uuid4()
    conversation = await create_conversation(db_session, "agent-1", user_id, "Test chat")
    question = await add_message(db_session, conversation.id, "user", "What is 2+2?")
    await db_session.commit()
    return conversation, question, user_id


# --------------------------------------------------------------- Regenerate (8.1.6)


async def test_regenerate_response_creates_new_message_and_history(monkeypatch, db_session):
    """Validation criterion: la régénération fonctionne."""
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("First answer")))
    conversation, question, user_id = await _seed_conversation(db_session)
    answer = await add_message(db_session, conversation.id, "assistant", "First answer")
    await db_session.commit()

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("Second answer")))
    new_message = await regenerate_response(db_session, conversation.id, answer.id, user_id)
    await db_session.commit()

    assert new_message.content == "Second answer"
    assert new_message.id != answer.id


async def test_regenerate_response_rejects_non_assistant_message(db_session):
    conversation, question, user_id = await _seed_conversation(db_session)
    with pytest.raises(MessageActionError):
        await regenerate_response(db_session, conversation.id, question.id, user_id)


async def test_regenerate_response_rejects_wrong_owner(monkeypatch, db_session):
    conversation, question, user_id = await _seed_conversation(db_session)
    answer = await add_message(db_session, conversation.id, "assistant", "Answer")
    await db_session.commit()

    with pytest.raises(MessageActionError):
        await regenerate_response(db_session, conversation.id, answer.id, uuid.uuid4())


async def test_regenerate_response_surfaces_llm_failure(monkeypatch, db_session):
    """Validation criterion: robustesse -- échec de génération."""
    conversation, question, user_id = await _seed_conversation(db_session)
    answer = await add_message(db_session, conversation.id, "assistant", "Answer")
    await db_session.commit()

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(side_effect=litellm.exceptions.AuthenticationError(
        message="bad key", llm_provider="anthropic", model="claude",
    )))
    with pytest.raises(MessageActionError):
        await regenerate_response(db_session, conversation.id, answer.id, user_id)


# ------------------------------------------------------------- Edit question (8.1.7)


async def test_edit_question_saves_history_and_updates_content(db_session):
    """Validation criterion: l'édition de question fonctionne."""
    conversation, question, user_id = await _seed_conversation(db_session)

    updated = await edit_question(db_session, question.id, "What is 3+3?", user_id)
    await db_session.commit()

    assert updated.content == "What is 3+3?"
    history = await get_edit_history(db_session, question.id)
    assert len(history) == 1
    assert history[0].content == "What is 2+2?"
    assert history[0].version == 1


async def test_edit_question_rejects_empty_content(db_session):
    conversation, question, user_id = await _seed_conversation(db_session)
    with pytest.raises(MessageActionError):
        await edit_question(db_session, question.id, "   ", user_id)


async def test_edit_question_rejects_editing_assistant_message(monkeypatch, db_session):
    conversation, question, user_id = await _seed_conversation(db_session)
    answer = await add_message(db_session, conversation.id, "assistant", "Answer")
    await db_session.commit()

    with pytest.raises(MessageActionError):
        await edit_question(db_session, answer.id, "new content", user_id)


async def test_revert_to_version_restores_prior_content_as_new_edit(db_session):
    conversation, question, user_id = await _seed_conversation(db_session)
    await edit_question(db_session, question.id, "Second version", user_id)
    await db_session.commit()

    reverted = await revert_to_version(db_session, question.id, 1, user_id)
    await db_session.commit()

    assert reverted.content == "What is 2+2?"
    history = await get_edit_history(db_session, question.id)
    assert len(history) == 2


async def test_regenerate_from_edited_question_replaces_existing_reply(monkeypatch, db_session):
    conversation, question, user_id = await _seed_conversation(db_session)
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("Old answer")))
    old_answer = await add_message(db_session, conversation.id, "assistant", "Old answer")
    await db_session.commit()

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("New answer")))
    new_reply = await regenerate_from_edited_question(db_session, question.id, "Edited question", user_id)
    await db_session.commit()

    assert new_reply.content == "New answer"
    assert new_reply.id != old_answer.id


# ------------------------------------------------------------------- Retry (8.1.8)


async def test_retry_message_generates_missing_reply(monkeypatch, db_session):
    """Validation criterion: le réessai fonctionne."""
    conversation, question, user_id = await _seed_conversation(db_session)
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("Answer via retry")))

    new_reply = await retry_message(db_session, question.id, user_id)
    await db_session.commit()

    assert new_reply.content == "Answer via retry"
    assert await get_retry_count(db_session, question.id) == 1


async def test_retry_message_rejects_when_reply_already_exists(monkeypatch, db_session):
    conversation, question, user_id = await _seed_conversation(db_session)
    await add_message(db_session, conversation.id, "assistant", "Already answered")
    await db_session.commit()

    with pytest.raises(MessageActionError):
        await retry_message(db_session, question.id, user_id)


async def test_retry_message_respects_the_attempt_limit(monkeypatch, db_session):
    """Validation criterion: la limite de tentatives est respectée."""
    conversation, question, user_id = await _seed_conversation(db_session)
    question.retry_count = settings.RETRY_MAX_ATTEMPTS
    await db_session.commit()

    with pytest.raises(MessageActionError):
        await retry_message(db_session, question.id, user_id)


async def test_is_retryable_false_once_answered(monkeypatch, db_session):
    conversation, question, user_id = await _seed_conversation(db_session)
    assert await is_retryable(db_session, question) is True

    await add_message(db_session, conversation.id, "assistant", "Answer")
    await db_session.commit()
    await db_session.refresh(question)
    assert await is_retryable(db_session, question) is False


# ---------------------------------------------------------------- Feedback (8.1.9)


async def test_add_feedback_creates_row(db_session):
    """Validation criterion: l'ajout de feedback fonctionne."""
    conversation, question, user_id = await _seed_conversation(db_session)
    answer = await add_message(db_session, conversation.id, "assistant", "Answer")
    await db_session.commit()

    feedback = await add_feedback(db_session, answer.id, user_id, "positive", comment="Great!")
    await db_session.commit()

    assert feedback.rating == "positive"
    assert feedback.comment == "Great!"


async def test_add_feedback_rejects_invalid_rating(db_session):
    conversation, question, user_id = await _seed_conversation(db_session)
    answer = await add_message(db_session, conversation.id, "assistant", "Answer")
    await db_session.commit()

    with pytest.raises(MessageActionError):
        await add_feedback(db_session, answer.id, user_id, "meh")


async def test_add_feedback_upserts_on_same_user_and_message(db_session):
    conversation, question, user_id = await _seed_conversation(db_session)
    answer = await add_message(db_session, conversation.id, "assistant", "Answer")
    await db_session.commit()

    first = await add_feedback(db_session, answer.id, user_id, "positive")
    await db_session.commit()
    second = await add_feedback(db_session, answer.id, user_id, "negative")
    await db_session.commit()

    assert first.id == second.id
    feedback_list = await get_feedback(db_session, answer.id)
    assert len(feedback_list) == 1
    assert feedback_list[0].rating == "negative"


async def test_update_feedback_modifies_existing_row(db_session):
    """Validation criterion: la modification fonctionne."""
    conversation, question, user_id = await _seed_conversation(db_session)
    answer = await add_message(db_session, conversation.id, "assistant", "Answer")
    await db_session.commit()
    feedback = await add_feedback(db_session, answer.id, user_id, "positive")
    await db_session.commit()

    updated = await update_feedback(db_session, feedback.id, comment="Changed my mind")
    await db_session.commit()

    assert updated.comment == "Changed my mind"
    assert updated.rating == "positive"


async def test_delete_feedback_removes_row(db_session):
    """Validation criterion: la suppression fonctionne."""
    conversation, question, user_id = await _seed_conversation(db_session)
    answer = await add_message(db_session, conversation.id, "assistant", "Answer")
    await db_session.commit()
    feedback = await add_feedback(db_session, answer.id, user_id, "positive")
    await db_session.commit()

    deleted = await delete_feedback(db_session, feedback.id)
    await db_session.commit()

    assert deleted is True
    assert await get_feedback(db_session, answer.id) == []


async def test_get_feedback_stats_aggregates_correctly(db_session):
    """Validation criterion: les statistiques sont correctes."""
    from api.models.organization import Organization

    org = Organization(name="Test Org", slug=f"test-org-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()

    conversation, question, user_id = await _seed_conversation(db_session)
    conversation.organization_id = org.id
    answer1 = await add_message(db_session, conversation.id, "assistant", "Answer 1")
    answer2 = await add_message(db_session, conversation.id, "assistant", "Answer 2")
    await db_session.commit()

    await add_feedback(db_session, answer1.id, user_id, "positive")
    await add_feedback(db_session, answer2.id, uuid.uuid4(), "negative")
    await db_session.commit()

    stats = await get_feedback_stats(db_session, org.id)
    assert stats["total"] == 2
    assert stats["positive"] == 1
    assert stats["negative"] == 1
    assert stats["positive_rate"] == 0.5


# ------------------------------------------------------------------- endpoints --

from sqlalchemy import select  # noqa: E402

from api.models.user import User  # noqa: E402


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def test_regenerate_endpoint(monkeypatch, client, db_session, register_payload):
    token, user = await _register(client, db_session, register_payload["email"], register_payload["password"])
    created = await client.post("/conversations", json={"agent_id": "agent-1", "title": "T"}, headers=_auth_header(token))
    conversation_id = created.json()["id"]
    await client.post(f"/conversations/{conversation_id}/messages", json={"role": "user", "content": "hi"}, headers=_auth_header(token))
    answer = await client.post(f"/conversations/{conversation_id}/messages", json={"role": "assistant", "content": "old"}, headers=_auth_header(token))
    message_id = answer.json()["id"]

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("regenerated")))
    response = await client.post(f"/conversations/{conversation_id}/messages/{message_id}/regenerate", json={}, headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json()["content"] == "regenerated"


async def test_edit_and_regenerate_endpoint(monkeypatch, client, db_session, register_payload):
    token, user = await _register(client, db_session, register_payload["email"], register_payload["password"])
    created = await client.post("/conversations", json={"agent_id": "agent-1", "title": "T"}, headers=_auth_header(token))
    conversation_id = created.json()["id"]
    question = await client.post(f"/conversations/{conversation_id}/messages", json={"role": "user", "content": "hi"}, headers=_auth_header(token))
    message_id = question.json()["id"]

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("new answer")))
    response = await client.post(f"/conversations/{conversation_id}/messages/{message_id}/edit", json={"content": "edited"}, headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json()["content"] == "new answer"


async def test_retry_endpoint(monkeypatch, client, db_session, register_payload):
    token, user = await _register(client, db_session, register_payload["email"], register_payload["password"])
    created = await client.post("/conversations", json={"agent_id": "agent-1", "title": "T"}, headers=_auth_header(token))
    conversation_id = created.json()["id"]
    question = await client.post(f"/conversations/{conversation_id}/messages", json={"role": "user", "content": "hi"}, headers=_auth_header(token))
    message_id = question.json()["id"]

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("answered")))
    response = await client.post(f"/conversations/{conversation_id}/messages/{message_id}/retry", headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json()["retry_count"] == 1


async def test_regenerate_endpoint_rejects_other_users_conversation(client, db_session, register_payload):
    """Validation criterion: sécurité -- les permissions sont respectées."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    other_token, other = await _register(client, db_session, "other-msg-actions@example.com")
    created = await client.post("/conversations", json={"agent_id": "agent-1", "title": "T"}, headers=_auth_header(owner_token))
    conversation_id = created.json()["id"]
    answer = await client.post(f"/conversations/{conversation_id}/messages", json={"role": "assistant", "content": "old"}, headers=_auth_header(owner_token))
    message_id = answer.json()["id"]

    response = await client.post(f"/conversations/{conversation_id}/messages/{message_id}/regenerate", json={}, headers=_auth_header(other_token))
    assert response.status_code == 404


async def test_feedback_endpoints(client, db_session, register_payload):
    token, user = await _register(client, db_session, register_payload["email"], register_payload["password"])
    created = await client.post("/conversations", json={"agent_id": "agent-1", "title": "T"}, headers=_auth_header(token))
    conversation_id = created.json()["id"]
    answer = await client.post(f"/conversations/{conversation_id}/messages", json={"role": "assistant", "content": "old"}, headers=_auth_header(token))
    message_id = answer.json()["id"]

    created_feedback = await client.post(f"/messages/{message_id}/feedback", json={"rating": "positive"}, headers=_auth_header(token))
    assert created_feedback.status_code == 200
    feedback_id = created_feedback.json()["id"]

    listing = await client.get(f"/messages/{message_id}/feedback", headers=_auth_header(token))
    assert len(listing.json()) == 1

    updated = await client.patch(f"/feedback/{feedback_id}", json={"comment": "nice"}, headers=_auth_header(token))
    assert updated.status_code == 200
    assert updated.json()["comment"] == "nice"

    deleted = await client.delete(f"/feedback/{feedback_id}", headers=_auth_header(token))
    assert deleted.status_code == 204


async def test_feedback_endpoint_rejects_other_users_message(client, db_session, register_payload):
    """Validation criterion: sécurité -- les évaluations sont isolées."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    other_token, other = await _register(client, db_session, "other-feedback@example.com")
    created = await client.post("/conversations", json={"agent_id": "agent-1", "title": "T"}, headers=_auth_header(owner_token))
    conversation_id = created.json()["id"]
    answer = await client.post(f"/conversations/{conversation_id}/messages", json={"role": "assistant", "content": "old"}, headers=_auth_header(owner_token))
    message_id = answer.json()["id"]

    response = await client.post(f"/messages/{message_id}/feedback", json={"rating": "positive"}, headers=_auth_header(other_token))
    assert response.status_code == 404

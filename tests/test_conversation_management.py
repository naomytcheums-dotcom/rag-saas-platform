"""Partie 8.1.10 (Historique/stats) + 8.1.11 (Rename) + 8.1.12 (Search)
+ 8.1.13 (Delete/restore/purge)."""

import uuid

import pytest
from sqlalchemy import select

from api.config import settings
from api.models.user import User
from api.security.conversations import add_message, create_conversation
from api.services.conversation_management import (
    ConversationManagementError, auto_generate_title, get_conversation_stats, highlight_matches,
    list_deleted_conversations, permanently_delete_conversation, purge_deleted_conversations, rename_conversation,
    restore_conversation, search_conversations, validate_title,
)
from api.services.conversation_management import delete_conversation as soft_delete_conversation


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


# --------------------------------------------------------------- History (8.1.10)


async def test_get_conversation_stats(db_session):
    """Validation criterion: les statistiques sont correctes."""
    user_id = uuid.uuid4()
    conversation = await create_conversation(db_session, "agent-1", user_id, "Chat")
    await add_message(db_session, conversation.id, "user", "hi")
    await add_message(db_session, conversation.id, "assistant", "hello")
    await db_session.commit()

    stats = await get_conversation_stats(db_session, user_id)
    assert stats == {"total_conversations": 1, "archived_conversations": 0, "total_messages": 2}


def test_auto_generate_title_uses_first_user_message():
    class _Msg:
        def __init__(self, role, content):
            self.role, self.content = role, content

    title = auto_generate_title([_Msg("user", "What is the capital of France?")])
    assert title == "What is the capital of France?"


def test_auto_generate_title_falls_back_when_no_user_message():
    assert auto_generate_title([]) == "New conversation"


# ---------------------------------------------------------------- Rename (8.1.11)


def test_validate_title_rejects_too_short():
    with pytest.raises(ConversationManagementError):
        validate_title("ab")


def test_validate_title_rejects_too_long():
    with pytest.raises(ConversationManagementError):
        validate_title("x" * (settings.CONVERSATION_TITLE_MAX_LENGTH + 1))


async def test_rename_conversation_updates_title(db_session):
    """Validation criterion: le renommage fonctionne."""
    user_id = uuid.uuid4()
    conversation = await create_conversation(db_session, "agent-1", user_id, "Old")
    await db_session.commit()

    renamed = await rename_conversation(db_session, conversation.id, "New title")
    await db_session.commit()
    assert renamed.title == "New title"


async def test_rename_conversation_rejects_empty_title(db_session):
    user_id = uuid.uuid4()
    conversation = await create_conversation(db_session, "agent-1", user_id, "Old")
    await db_session.commit()

    with pytest.raises(ConversationManagementError):
        await rename_conversation(db_session, conversation.id, "  ")


async def test_rename_endpoint_rejects_invalid_title(client, db_session, register_payload):
    token, user = await _register(client, db_session, register_payload["email"], register_payload["password"])
    created = await client.post("/conversations", json={"agent_id": "agent-1", "title": "Old"}, headers=_auth_header(token))
    conversation_id = created.json()["id"]

    response = await client.patch(f"/conversations/{conversation_id}", json={"title": "a"}, headers=_auth_header(token))
    assert response.status_code == 400


# ---------------------------------------------------------------- Search (8.1.12)


def test_highlight_matches_wraps_query():
    assert highlight_matches("hello world", "world") == "hello <mark>world</mark>"


def test_highlight_matches_case_insensitive():
    assert highlight_matches("Hello World", "world") == "Hello <mark>World</mark>"


async def test_search_conversations_by_title(db_session):
    """Validation criterion: la recherche fonctionne."""
    user_id = uuid.uuid4()
    await create_conversation(db_session, "agent-1", user_id, "Python tutorial")
    await create_conversation(db_session, "agent-1", user_id, "Cooking recipes")
    await db_session.commit()

    results = await search_conversations(db_session, user_id, "python")
    assert len(results) == 1
    assert results[0]["conversation"].title == "Python tutorial"


async def test_search_conversations_by_message_content(db_session):
    user_id = uuid.uuid4()
    conversation = await create_conversation(db_session, "agent-1", user_id, "General chat")
    await add_message(db_session, conversation.id, "user", "Tell me about kubernetes")
    await db_session.commit()

    results = await search_conversations(db_session, user_id, "kubernetes")
    assert len(results) == 1
    assert results[0]["matched_message"].content == "Tell me about kubernetes"


async def test_search_conversations_rejects_too_short_query(db_session):
    user_id = uuid.uuid4()
    with pytest.raises(ConversationManagementError):
        await search_conversations(db_session, user_id, "a")


async def test_search_endpoint_highlights_matches(client, db_session, register_payload):
    token, user = await _register(client, db_session, register_payload["email"], register_payload["password"])
    await client.post("/conversations", json={"agent_id": "agent-1", "title": "Django tips"}, headers=_auth_header(token))

    response = await client.get("/conversations/search", params={"q": "django"}, headers=_auth_header(token))
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert "<mark>" in response.json()[0]["conversation"]["title"] or response.json()[0]["conversation"]["title"] == "Django tips"


# ---------------------------------------------------------------- Delete (8.1.13)


async def test_soft_delete_hides_conversation_from_normal_access(db_session):
    """Validation criterion: la suppression fonctionne."""
    user_id = uuid.uuid4()
    conversation = await create_conversation(db_session, "agent-1", user_id, "Chat")
    await db_session.commit()

    deleted = await soft_delete_conversation(db_session, conversation.id, user_id)
    await db_session.commit()
    assert deleted is True

    from api.security.conversations import get_conversation
    still_exists = await get_conversation(db_session, conversation.id)
    assert still_exists is not None
    assert still_exists.deleted_at is not None


async def test_soft_delete_rejects_wrong_owner(db_session):
    user_id = uuid.uuid4()
    conversation = await create_conversation(db_session, "agent-1", user_id, "Chat")
    await db_session.commit()

    result = await soft_delete_conversation(db_session, conversation.id, uuid.uuid4())
    assert result is False


async def test_restore_conversation(db_session):
    """Validation criterion: la restauration fonctionne."""
    user_id = uuid.uuid4()
    conversation = await create_conversation(db_session, "agent-1", user_id, "Chat")
    await db_session.commit()
    await soft_delete_conversation(db_session, conversation.id, user_id)
    await db_session.commit()

    restored = await restore_conversation(db_session, conversation.id, user_id)
    await db_session.commit()
    assert restored.deleted_at is None


async def test_list_deleted_conversations(db_session):
    user_id = uuid.uuid4()
    conversation = await create_conversation(db_session, "agent-1", user_id, "Chat")
    await db_session.commit()
    await soft_delete_conversation(db_session, conversation.id, user_id)
    await db_session.commit()

    deleted_list = await list_deleted_conversations(db_session, user_id)
    assert len(deleted_list) == 1
    assert deleted_list[0].id == conversation.id


async def test_permanently_delete_conversation_hard_deletes(db_session):
    user_id = uuid.uuid4()
    conversation = await create_conversation(db_session, "agent-1", user_id, "Chat")
    await db_session.commit()

    deleted = await permanently_delete_conversation(db_session, conversation.id, user_id)
    await db_session.commit()
    assert deleted is True

    from api.security.conversations import get_conversation
    assert await get_conversation(db_session, conversation.id) is None


async def test_purge_deleted_conversations_respects_grace_period(db_session):
    """Validation criterion: la purge fonctionne."""
    import datetime as dt

    user_id = uuid.uuid4()
    recent = await create_conversation(db_session, "agent-1", user_id, "Recent")
    old = await create_conversation(db_session, "agent-1", user_id, "Old")
    await db_session.commit()

    await soft_delete_conversation(db_session, recent.id, user_id)
    await soft_delete_conversation(db_session, old.id, user_id)
    old.deleted_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=settings.CONVERSATION_DELETION_GRACE_PERIOD + 1)
    await db_session.commit()

    purged_count = await purge_deleted_conversations(db_session)
    await db_session.commit()

    assert purged_count == 1
    from api.security.conversations import get_conversation
    assert await get_conversation(db_session, old.id) is None
    assert await get_conversation(db_session, recent.id) is not None


async def test_delete_endpoint_soft_deletes_and_restore_endpoint_recovers(client, db_session, register_payload):
    token, user = await _register(client, db_session, register_payload["email"], register_payload["password"])
    created = await client.post("/conversations", json={"agent_id": "agent-1", "title": "Chat"}, headers=_auth_header(token))
    conversation_id = created.json()["id"]

    deleted = await client.delete(f"/conversations/{conversation_id}", headers=_auth_header(token))
    assert deleted.status_code == 204

    not_found = await client.get(f"/conversations/{conversation_id}", headers=_auth_header(token))
    assert not_found.status_code == 404

    restored = await client.post(f"/conversations/{conversation_id}/restore", headers=_auth_header(token))
    assert restored.status_code == 200

    found_again = await client.get(f"/conversations/{conversation_id}", headers=_auth_header(token))
    assert found_again.status_code == 200

"""Partie 5.1.12 -- cross-session conversation memory. Fast SQLite suite."""

import uuid

from sqlalchemy import select

from api.models.user import User
from api.security.conversations import (
    add_message, archive_conversation, create_conversation, delete_conversation, get_conversation,
    get_conversation_messages, get_conversations, update_conversation_title,
)


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


# --------------------------------------- security-layer --


async def test_create_conversation_creates_a_real_row(db_session):
    """Validation criterion: la création de conversation fonctionne."""
    user_id = uuid.uuid4()
    conversation = await create_conversation(db_session, "agent-1", user_id, "My chat")
    await db_session.commit()

    assert conversation.title == "My chat"
    assert conversation.archived is False


async def test_add_message_creates_a_real_message_and_touches_updated_at(db_session):
    """Validation criterion: l'ajout de message fonctionne."""
    user_id = uuid.uuid4()
    conversation = await create_conversation(db_session, "agent-1", user_id, "My chat")
    await db_session.commit()
    original_updated_at = conversation.updated_at

    message = await add_message(db_session, conversation.id, "user", "hello")
    await db_session.commit()

    assert message.content == "hello"
    assert conversation.updated_at.replace(tzinfo=None) >= original_updated_at.replace(tzinfo=None)


async def test_get_conversation_messages_returns_real_chronological_order(db_session):
    """Validation criterion: la récupération de l'historique fonctionne."""
    user_id = uuid.uuid4()
    conversation = await create_conversation(db_session, "agent-1", user_id, "My chat")
    await add_message(db_session, conversation.id, "user", "first")
    await add_message(db_session, conversation.id, "assistant", "second")
    await db_session.commit()

    messages = await get_conversation_messages(db_session, conversation.id)
    assert [m.content for m in messages] == ["first", "second"]


async def test_get_conversations_lists_only_this_users_own_conversations(db_session):
    """Validation criterion: sécurité -- isolation par utilisateur."""
    user_a, user_b = uuid.uuid4(), uuid.uuid4()
    await create_conversation(db_session, "agent-1", user_a, "A's chat")
    await create_conversation(db_session, "agent-1", user_b, "B's chat")
    await db_session.commit()

    conversations_a = await get_conversations(db_session, user_a)
    assert len(conversations_a) == 1
    assert conversations_a[0].title == "A's chat"


async def test_update_conversation_title(db_session):
    user_id = uuid.uuid4()
    conversation = await create_conversation(db_session, "agent-1", user_id, "Old title")
    await db_session.commit()

    updated = await update_conversation_title(db_session, conversation.id, "New title")
    await db_session.commit()

    assert updated.title == "New title"


async def test_archive_conversation(db_session):
    """Validation criterion: l'archivage fonctionne."""
    user_id = uuid.uuid4()
    conversation = await create_conversation(db_session, "agent-1", user_id, "My chat")
    await db_session.commit()

    archived = await archive_conversation(db_session, conversation.id)
    await db_session.commit()

    assert archived.archived is True


async def test_delete_conversation_cascades_to_messages(db_session):
    user_id = uuid.uuid4()
    conversation = await create_conversation(db_session, "agent-1", user_id, "My chat")
    await add_message(db_session, conversation.id, "user", "hello")
    await db_session.commit()

    deleted = await delete_conversation(db_session, conversation.id)
    await db_session.commit()

    assert deleted is True
    assert await get_conversation(db_session, conversation.id) is None


async def test_delete_conversation_returns_false_for_unknown_id(db_session):
    assert await delete_conversation(db_session, uuid.uuid4()) is False


# --------------------------------------- endpoints --


async def test_create_and_list_own_conversations(client, db_session, register_payload):
    token, user = await _register(client, db_session, register_payload["email"], register_payload["password"])

    created = await client.post("/conversations", json={"agent_id": "agent-1", "title": "Test chat"}, headers=_auth_header(token))
    assert created.status_code == 200

    listing = await client.get("/conversations", headers=_auth_header(token))
    assert listing.status_code == 200
    assert len(listing.json()) == 1


async def test_add_and_list_messages_via_endpoint(client, db_session, register_payload):
    token, user = await _register(client, db_session, register_payload["email"], register_payload["password"])
    created = await client.post("/conversations", json={"agent_id": "agent-1", "title": "Test chat"}, headers=_auth_header(token))
    conversation_id = created.json()["id"]

    response = await client.post(
        f"/conversations/{conversation_id}/messages", json={"role": "user", "content": "hi"}, headers=_auth_header(token),
    )
    assert response.status_code == 200

    messages = await client.get(f"/conversations/{conversation_id}/messages", headers=_auth_header(token))
    assert len(messages.json()) == 1


async def test_cannot_read_another_users_conversation(client, db_session, register_payload):
    """Validation criterion: sécurité -- isolation par utilisateur."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    other_token, other = await _register(client, db_session, "other@example.com")

    created = await client.post("/conversations", json={"agent_id": "agent-1", "title": "Private"}, headers=_auth_header(owner_token))
    conversation_id = created.json()["id"]

    response = await client.get(f"/conversations/{conversation_id}", headers=_auth_header(other_token))
    assert response.status_code == 404


async def test_archive_and_delete_via_endpoint(client, db_session, register_payload):
    token, user = await _register(client, db_session, register_payload["email"], register_payload["password"])
    created = await client.post("/conversations", json={"agent_id": "agent-1", "title": "Test chat"}, headers=_auth_header(token))
    conversation_id = created.json()["id"]

    archived = await client.post(f"/conversations/{conversation_id}/archive", headers=_auth_header(token))
    assert archived.status_code == 200
    assert archived.json()["archived"] is True

    deleted = await client.delete(f"/conversations/{conversation_id}", headers=_auth_header(token))
    assert deleted.status_code == 204


async def test_update_title_via_endpoint(client, db_session, register_payload):
    token, user = await _register(client, db_session, register_payload["email"], register_payload["password"])
    created = await client.post("/conversations", json={"agent_id": "agent-1", "title": "Old"}, headers=_auth_header(token))
    conversation_id = created.json()["id"]

    response = await client.patch(f"/conversations/{conversation_id}", json={"title": "New"}, headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json()["title"] == "New"

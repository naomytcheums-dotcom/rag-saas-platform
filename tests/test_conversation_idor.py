"""P2C-4: private user-owned conversation and foreign message parent binding."""

from unittest.mock import AsyncMock

from api.models.conversation import Conversation, ConversationMessage
from api.models.message_actions import MessageEditHistory
from test_document_idor import denied, make_tenants, snapshot


async def test_conversation_idor(client, db_session, monkeypatch):
    (owner, org_a, user_a), (attacker, org_b, user_b) = await make_tenants(
        client, db_session, monkeypatch, "conversation"
    )
    private = Conversation(
        user_id=user_a, organization_id=org_a, agent_id="p2c-agent-a",
        title="private-conversation", is_public=False,
    )
    own = Conversation(
        user_id=user_b, organization_id=org_b, agent_id="p2c-agent-b",
        title="attacker-own-conversation", is_public=False,
    )
    db_session.add_all([private, own])
    await db_session.flush()
    message = ConversationMessage(
        conversation_id=private.id, role="user", content="private-message"
    )
    db_session.add(message)
    await db_session.flush()
    history = MessageEditHistory(
        message_id=message.id, version=1, content="private-prior-content", edited_by=user_a
    )
    db_session.add(history)
    await db_session.commit()
    private_id, own_id, message_id = private.id, own.id, message.id
    baseline = await snapshot(db_session, private, own, message, history)
    regenerate, retry = AsyncMock(), AsyncMock()
    monkeypatch.setattr("api.routers.conversations.regenerate_response", regenerate)
    monkeypatch.setattr("api.routers.conversations.retry_message", retry)
    control = await client.get(f"/conversations/{private_id}", headers=owner)
    assert control.status_code == 200, control.text
    control = await client.get(
        f"/conversations/{private_id}/messages/{message_id}/edit-history", headers=owner
    )
    assert control.status_code == 200
    assert control.json()[0]["content"] == "private-prior-content"
    violations = []
    for suffix in ("", "/messages", "/shares", f"/messages/{message_id}/edit-history"):
        await denied(client, "GET", f"/conversations/{private_id}{suffix}", attacker, violations)
    export = await denied(
        client, "GET", f"/conversations/{private_id}/export/json", attacker, violations,
        expected=(400,),
    )
    if "not found" not in export.text.lower():
        violations.append("Export did not return an explicit not-found denial")
    await denied(
        client, "PATCH", f"/conversations/{private_id}", attacker, violations,
        json={"title": "attacker-rename"},
    )
    for action in ("archive", "restore", "share"):
        await denied(
            client, "POST", f"/conversations/{private_id}/{action}", attacker, violations,
            json={},
        )
    for action in ("regenerate", "retry"):
        await denied(
            client, "POST", f"/conversations/{private_id}/messages/{message_id}/{action}",
            attacker, violations, json={},
        )
    await denied(client, "DELETE", f"/conversations/{private_id}", attacker, violations)
    leaked = await denied(
        client, "GET", f"/conversations/{own_id}/messages/{message_id}/edit-history",
        attacker, violations,
    )
    if "private-prior-content" in leaked.text:
        violations.append("CONFIRMED: own conversation + foreign message ID leaks prior content")
    assert await snapshot(db_session, private, own, message, history) == baseline
    regenerate.assert_not_called()
    retry.assert_not_called()
    assert not violations, "\n".join(violations)

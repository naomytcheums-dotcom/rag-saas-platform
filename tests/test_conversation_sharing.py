"""Partie 8.1.15 (Share) + 8.1.16 (Public/Private)."""

import datetime as dt
import uuid

import pytest
from sqlalchemy import select

from api.models.user import User
from api.security.conversations import create_conversation
from api.services.conversation_sharing import (
    SharingError, can_view_conversation, create_share_link, delete_share_link, get_shared_conversation,
    increment_view_count, is_share_valid, list_public_conversations, list_share_links, set_conversation_visibility,
)


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


# --------------------------------------------------------------------- Share (8.1.15)


async def test_create_share_link(db_session):
    """Validation criterion: la création de lien fonctionne."""
    user_id = uuid.uuid4()
    conversation = await create_conversation(db_session, "agent-1", user_id, "Chat")
    await db_session.commit()

    share = await create_share_link(db_session, conversation.id, user_id)
    await db_session.commit()

    assert len(share.token) > 20
    assert share.views == 0


async def test_get_shared_conversation_via_valid_token(db_session):
    """Validation criterion: l'accès public fonctionne."""
    user_id = uuid.uuid4()
    conversation = await create_conversation(db_session, "agent-1", user_id, "Chat")
    await db_session.commit()
    share = await create_share_link(db_session, conversation.id, user_id)
    await db_session.commit()

    result = await get_shared_conversation(db_session, share.token)
    assert result is not None
    assert result[0].id == conversation.id


async def test_get_shared_conversation_returns_none_for_unknown_token(db_session):
    assert await get_shared_conversation(db_session, "not-a-real-token") is None


async def test_expired_share_link_is_invalid(db_session):
    """Validation criterion: l'expiration fonctionne."""
    user_id = uuid.uuid4()
    conversation = await create_conversation(db_session, "agent-1", user_id, "Chat")
    await db_session.commit()
    expired_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
    share = await create_share_link(db_session, conversation.id, user_id, expires_at=expired_at)
    await db_session.commit()

    assert is_share_valid(share) is False
    assert await get_shared_conversation(db_session, share.token) is None


async def test_max_views_exhausted_makes_share_invalid(db_session):
    user_id = uuid.uuid4()
    conversation = await create_conversation(db_session, "agent-1", user_id, "Chat")
    await db_session.commit()
    share = await create_share_link(db_session, conversation.id, user_id, max_views=1)
    await db_session.commit()

    await increment_view_count(db_session, share.token)
    await db_session.commit()
    await db_session.refresh(share)

    assert is_share_valid(share) is False


async def test_delete_share_link(db_session):
    user_id = uuid.uuid4()
    conversation = await create_conversation(db_session, "agent-1", user_id, "Chat")
    await db_session.commit()
    share = await create_share_link(db_session, conversation.id, user_id)
    await db_session.commit()

    deleted = await delete_share_link(db_session, share.token, user_id)
    await db_session.commit()
    assert deleted is True
    assert await get_shared_conversation(db_session, share.token) is None


async def test_create_share_link_rejects_other_users_conversation(db_session):
    user_id = uuid.uuid4()
    conversation = await create_conversation(db_session, "agent-1", user_id, "Chat")
    await db_session.commit()

    with pytest.raises(SharingError):
        await create_share_link(db_session, conversation.id, uuid.uuid4())


async def test_share_endpoint_and_public_access(client, db_session, register_payload):
    token, user = await _register(client, db_session, register_payload["email"], register_payload["password"])
    created = await client.post("/conversations", json={"agent_id": "agent-1", "title": "Chat"}, headers=_auth_header(token))
    conversation_id = created.json()["id"]

    share_response = await client.post(f"/conversations/{conversation_id}/share", json={}, headers=_auth_header(token))
    assert share_response.status_code == 200
    share_token = share_response.json()["token"]

    public_response = await client.get(f"/share/{share_token}")
    assert public_response.status_code == 200
    assert public_response.json()["conversation"]["id"] == conversation_id

    listing = await client.get(f"/conversations/{conversation_id}/shares", headers=_auth_header(token))
    assert len(listing.json()) == 1

    deleted = await client.delete(f"/share/{share_token}", headers=_auth_header(token))
    assert deleted.status_code == 204


# ------------------------------------------------------------ Public/Private (8.1.16)


async def test_set_conversation_visibility(db_session):
    """Validation criterion: la visibilité est modifiable."""
    user_id = uuid.uuid4()
    conversation = await create_conversation(db_session, "agent-1", user_id, "Chat")
    await db_session.commit()

    updated = await set_conversation_visibility(db_session, conversation.id, user_id, True)
    await db_session.commit()
    assert updated.is_public is True


async def test_list_public_conversations_scoped_to_organization(db_session):
    """Validation criterion: les conversations publiques sont listées."""
    from api.models.organization import Organization

    org = Organization(name="Org", slug=f"org-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()

    user_id = uuid.uuid4()
    public_conv = await create_conversation(db_session, "agent-1", user_id, "Public", organization_id=org.id)
    private_conv = await create_conversation(db_session, "agent-1", user_id, "Private", organization_id=org.id)
    await db_session.commit()
    await set_conversation_visibility(db_session, public_conv.id, user_id, True)
    await db_session.commit()

    results = await list_public_conversations(db_session, org.id)
    assert len(results) == 1
    assert results[0].title == "Public"


async def test_can_view_conversation_rules(db_session):
    """Validation criterion: sécurité -- les permissions sont respectées."""
    owner_id, other_id = uuid.uuid4(), uuid.uuid4()
    conversation = await create_conversation(db_session, "agent-1", owner_id, "Chat")
    await db_session.commit()

    assert await can_view_conversation(db_session, conversation.id, owner_id) is True
    assert await can_view_conversation(db_session, conversation.id, other_id) is False
    assert await can_view_conversation(db_session, conversation.id, other_id, is_org_admin=True) is True

    await set_conversation_visibility(db_session, conversation.id, owner_id, True)
    await db_session.commit()
    assert await can_view_conversation(db_session, conversation.id, other_id) is True

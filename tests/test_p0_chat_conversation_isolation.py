"""P0 audit fixes TEN-001 / RAG-001 / RAG-017 -- conversation isolation.

`POST|GET /chat/stream` used to hand any `conversation_id` straight to the
orchestrator: a user of organization A could write into (and have the LLM
read the history of) a conversation of organization B. `POST /conversations`
also accepted an agent / organization the caller does not belong to.

No LLM, retrieval or network call is ever made: retrieval and the SSE
generator are replaced at the router boundary and the generator records
whether it was ever started."""

import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select

from api.models.agent import Agent
from api.models.conversation import Conversation, ConversationMessage
from api.models.organization import Organization, OrganizationMember, OrganizationRole
from api.models.user import User


def _bearer(token: str) -> dict:
    return {"Authorization": "Bearer " + token}


async def _register(client, db_session, email: str):
    payload = {"email": email, "password": "correct-horse-battery-staple", "accept_terms": True}
    token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return token, user


async def _org_with_agent(db_session, owner: User, label: str):
    org = Organization(name=f"{label} Org", slug=f"{label.lower()}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    db_session.add(OrganizationMember(organization_id=org.id, user_id=owner.id, role=OrganizationRole.owner))
    agent = Agent(organization_id=org.id, name=f"{label} Bot", system_prompt="You are helpful.")
    db_session.add(agent)
    await db_session.commit()
    return org, agent


async def _conversation(db_session, user: User, org_id, agent: Agent, title="Chat", **extra) -> Conversation:
    conversation = Conversation(agent_id=str(agent.id), user_id=user.id, organization_id=org_id, title=title, **extra)
    db_session.add(conversation)
    await db_session.commit()
    return conversation


async def _message_count(db_session) -> int:
    return await db_session.scalar(select(func.count()).select_from(ConversationMessage))


@pytest.fixture
def stream_spy(monkeypatch):
    """Replaces retrieval + the SSE generator; `spy.started` lists the
    kwargs of every generator that was created (i.e. every stream that
    would have touched conversation history)."""
    class Spy:
        started: list = []

    spy = Spy()
    spy.started = []
    spy.search = AsyncMock(return_value=[])

    def fake_stream(db, agent_id, message, **kwargs):
        spy.started.append({"agent_id": agent_id, "message": message, **kwargs})

        async def generator():
            yield "event: done\ndata: {}\n\n"

        return generator()

    monkeypatch.setattr("api.routers.chat_stream.search_with_context", spy.search)
    monkeypatch.setattr("api.routers.chat_stream.stream_agent_response", fake_stream)
    return spy


@pytest.fixture
async def two_tenants(client, db_session):
    token_a, user_a = await _register(client, db_session, "owner-a@example.com")
    token_b, user_b = await _register(client, db_session, "owner-b@example.com")
    org_a, agent_a = await _org_with_agent(db_session, user_a, "Alpha")
    org_b, agent_b = await _org_with_agent(db_session, user_b, "Bravo")
    conversation_b = await _conversation(db_session, user_b, org_b.id, agent_b, "B-PRIVATE")
    await ConversationMessageFactory.add(db_session, conversation_b.id, "B-PRIVATE history")
    return {
        "token_a": token_a, "user_a": user_a, "org_a": org_a, "agent_a": agent_a,
        "token_b": token_b, "user_b": user_b, "org_b": org_b, "agent_b": agent_b, "conversation_b": conversation_b,
    }


class ConversationMessageFactory:
    @staticmethod
    async def add(db_session, conversation_id, content, role="user") -> ConversationMessage:
        message = ConversationMessage(conversation_id=conversation_id, role=role, content=content)
        db_session.add(message)
        await db_session.commit()
        return message


# ------------------------------------------------------------- TEN-001 / RAG-001: /chat/stream


async def test_stream_without_conversation_still_works(client, two_tenants, stream_spy):
    t = two_tenants
    response = await client.post("/chat/stream", json={"agent_id": str(t["agent_a"].id), "message": "hi"}, headers=_bearer(t["token_a"]))

    assert response.status_code == 200
    assert len(stream_spy.started) == 1
    assert stream_spy.started[0]["conversation_id"] is None


async def test_stream_with_own_conversation_in_the_agents_org_still_works(client, db_session, two_tenants, stream_spy):
    t = two_tenants
    conversation = await _conversation(db_session, t["user_a"], t["org_a"].id, t["agent_a"], "mine")

    response = await client.post(
        "/chat/stream", json={"agent_id": str(t["agent_a"].id), "message": "hi", "conversation_id": str(conversation.id)},
        headers=_bearer(t["token_a"]),
    )
    get_response = await client.get(
        "/chat/stream", params={"agent_id": str(t["agent_a"].id), "message": "hi", "conversation_id": str(conversation.id)},
        headers=_bearer(t["token_a"]),
    )

    assert response.status_code == 200
    assert get_response.status_code == 200
    assert [call["conversation_id"] for call in stream_spy.started] == [conversation.id, conversation.id]
    assert all(call["user_id"] == t["user_a"].id and call["organization_id"] == t["org_a"].id for call in stream_spy.started)


async def test_exploit_org_a_user_cannot_stream_into_org_b_conversation(client, db_session, two_tenants, stream_spy):
    """The audited exploit: A's own agent + B's conversation_id."""
    t = two_tenants
    before = await _message_count(db_session)
    updated_before = t["conversation_b"].updated_at

    post = await client.post(
        "/chat/stream",
        json={"agent_id": str(t["agent_a"].id), "message": "CROSS-TENANT-WRITE-PROBE", "conversation_id": str(t["conversation_b"].id)},
        headers=_bearer(t["token_a"]),
    )
    get = await client.get(
        "/chat/stream",
        params={"agent_id": str(t["agent_a"].id), "message": "CROSS-TENANT-WRITE-PROBE", "conversation_id": str(t["conversation_b"].id)},
        headers=_bearer(t["token_a"]),
    )

    assert post.status_code == 404
    assert get.status_code == 404
    assert stream_spy.started == []  # no history read, no message written: the orchestrator was never reached
    stream_spy.search.assert_not_awaited()
    assert await _message_count(db_session) == before
    probe = await db_session.scalar(select(func.count()).select_from(ConversationMessage).where(ConversationMessage.content.like("%PROBE%")))
    assert probe == 0
    await db_session.refresh(t["conversation_b"])
    assert t["conversation_b"].updated_at == updated_before


async def test_cannot_stream_into_another_users_conversation_of_the_same_org(client, db_session, two_tenants, stream_spy):
    t = two_tenants
    colleague_token, colleague = await _register(client, db_session, "colleague@example.com")
    db_session.add(OrganizationMember(organization_id=t["org_a"].id, user_id=colleague.id, role=OrganizationRole.member))
    await db_session.commit()
    colleague_conversation = await _conversation(db_session, colleague, t["org_a"].id, t["agent_a"], "colleague's")

    response = await client.post(
        "/chat/stream", json={"agent_id": str(t["agent_a"].id), "message": "hi", "conversation_id": str(colleague_conversation.id)},
        headers=_bearer(t["token_a"]),
    )

    assert response.status_code == 404
    assert stream_spy.started == []


async def test_own_conversation_scoped_to_another_org_is_refused(client, db_session, two_tenants, stream_spy):
    t = two_tenants
    mismatched = await _conversation(db_session, t["user_a"], t["org_b"].id, t["agent_b"], "A's row pointing at org B")

    response = await client.post(
        "/chat/stream", json={"agent_id": str(t["agent_a"].id), "message": "hi", "conversation_id": str(mismatched.id)},
        headers=_bearer(t["token_a"]),
    )

    assert response.status_code == 404
    assert stream_spy.started == []


@pytest.mark.parametrize("kind", ["unknown", "soft_deleted", "no_organization"])
async def test_unknown_deleted_or_unscoped_conversation_is_404(client, db_session, two_tenants, stream_spy, kind):
    import datetime as dt

    t = two_tenants
    if kind == "unknown":
        conversation_id = uuid.uuid4()
    elif kind == "soft_deleted":
        conversation_id = (await _conversation(db_session, t["user_a"], t["org_a"].id, t["agent_a"], deleted_at=dt.datetime.now(dt.timezone.utc))).id
    else:
        conversation_id = (await _conversation(db_session, t["user_a"], None, t["agent_a"])).id

    response = await client.post(
        "/chat/stream", json={"agent_id": str(t["agent_a"].id), "message": "hi", "conversation_id": str(conversation_id)},
        headers=_bearer(t["token_a"]),
    )

    assert response.status_code == 404
    assert stream_spy.started == []


async def test_agent_of_an_organization_the_user_is_not_a_member_of_is_404(client, db_session, two_tenants, stream_spy):
    t = two_tenants

    response = await client.post(
        "/chat/stream", json={"agent_id": str(t["agent_b"].id), "message": "hi", "conversation_id": str(t["conversation_b"].id)},
        headers=_bearer(t["token_a"]),
    )

    assert response.status_code == 404
    assert stream_spy.started == []


# ------------------------------------------------------------- RAG-017: POST /conversations


async def test_create_conversation_nominal_cases_still_work(client, db_session, two_tenants):
    t = two_tenants

    legacy = await client.post("/conversations", json={"agent_id": "agent-1", "title": "legacy"}, headers=_bearer(t["token_a"]))
    scoped = await client.post(
        "/conversations", json={"agent_id": str(t["agent_a"].id), "title": "mine", "organization_id": str(t["org_a"].id)},
        headers=_bearer(t["token_a"]),
    )
    agent_only = await client.post("/conversations", json={"agent_id": str(t["agent_a"].id), "title": "mine"}, headers=_bearer(t["token_a"]))

    assert (legacy.status_code, scoped.status_code, agent_only.status_code) == (200, 200, 200)
    row = await db_session.get(Conversation, uuid.UUID(scoped.json()["id"]))
    assert row.organization_id == t["org_a"].id and row.user_id == t["user_a"].id


async def test_create_conversation_with_another_orgs_agent_is_404_and_writes_nothing(client, db_session, two_tenants):
    t = two_tenants
    before = await db_session.scalar(select(func.count()).select_from(Conversation))

    without_org = await client.post("/conversations", json={"agent_id": str(t["agent_b"].id), "title": "x"}, headers=_bearer(t["token_a"]))
    with_org_b = await client.post(
        "/conversations", json={"agent_id": str(t["agent_b"].id), "title": "x", "organization_id": str(t["org_b"].id)},
        headers=_bearer(t["token_a"]),
    )

    assert (without_org.status_code, with_org_b.status_code) == (404, 404)
    assert await db_session.scalar(select(func.count()).select_from(Conversation)) == before


async def test_create_conversation_in_an_organization_the_user_is_not_a_member_of_is_404(client, db_session, two_tenants):
    t = two_tenants
    before = await db_session.scalar(select(func.count()).select_from(Conversation))

    response = await client.post(
        "/conversations", json={"agent_id": "agent-1", "title": "x", "organization_id": str(t["org_b"].id)}, headers=_bearer(t["token_a"]),
    )

    assert response.status_code == 404
    assert await db_session.scalar(select(func.count()).select_from(Conversation)) == before


async def test_create_conversation_agent_and_organization_must_match(client, db_session, two_tenants):
    t = two_tenants
    org_c, _agent_c = await _org_with_agent(db_session, t["user_a"], "Charlie")  # A is a member of both A and C

    response = await client.post(
        "/conversations", json={"agent_id": str(t["agent_a"].id), "title": "x", "organization_id": str(org_c.id)},
        headers=_bearer(t["token_a"]),
    )

    assert response.status_code == 404


# ------------------------------------------------------------- other routes taking a conversation_id: already guarded


async def test_rest_routes_on_another_tenants_conversation_stay_refused(client, db_session, two_tenants):
    t = two_tenants
    message = await ConversationMessageFactory.add(db_session, t["conversation_b"].id, "B answer", role="assistant")
    cid, headers = t["conversation_b"].id, _bearer(t["token_a"])
    before = await _message_count(db_session)

    assert (await client.get(f"/conversations/{cid}", headers=headers)).status_code == 404
    assert (await client.get(f"/conversations/{cid}/messages", headers=headers)).status_code == 404
    assert (await client.post(f"/conversations/{cid}/messages", json={"role": "user", "content": "x"}, headers=headers)).status_code == 404
    assert (await client.post(f"/conversations/{cid}/messages/{message.id}/regenerate", headers=headers)).status_code == 404
    assert (await client.post(f"/conversations/{cid}/messages/{message.id}/retry", headers=headers)).status_code == 404
    assert (await client.post(f"/messages/{message.id}/feedback", json={"rating": "positive"}, headers=headers)).status_code == 404
    assert (await client.get(f"/conversations/{cid}/export/json", headers=headers)).status_code != 200
    assert await _message_count(db_session) == before

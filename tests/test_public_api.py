"""Partie 9.1.1-9.1.9 -- the public /v1/* API."""

import uuid
from unittest.mock import AsyncMock

import litellm
import pytest
from litellm.types.utils import Choices, Message, ModelResponse

from api.config import settings
from api.services.organization_api_keys import (
    OrganizationAPIKeyError, generate_organization_api_key, get_organization_from_api_key, revoke_api_key,
    validate_scopes, verify_api_key,
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


def _api_key_header(api_key: str) -> dict:
    return {"X-API-Key": api_key}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    from sqlalchemy import select

    from api.models.user import User

    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _make_org_with_api_key(client, db_session, register_payload, scopes):
    token, user = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_id = (await client.post("/organizations", json={"name": "Public API Org"}, headers=_auth_header(token))).json()["id"]
    created = await client.post(
        f"/organizations/{org_id}/api-keys", json={"name": "test-key", "scopes": scopes}, headers=_auth_header(token),
    )
    api_key = created.json()["key"]
    return token, org_id, api_key


# ---------------------------------------------------------------- Key management (unit)


async def test_generate_and_verify_organization_api_key(db_session):
    """Validation criterion: les clés API sont correctement validées."""
    org_id = uuid.uuid4()
    row, plaintext = await generate_organization_api_key(db_session, org_id, "key-1", ["chat:write"])
    await db_session.commit()

    verified = await verify_api_key(db_session, plaintext)
    assert verified is not None
    assert verified.id == row.id
    assert verified.last_used_at is not None


async def test_verify_api_key_rejects_unknown_key(db_session):
    assert await verify_api_key(db_session, "pk_not_a_real_key") is None


async def test_verify_api_key_rejects_revoked_key(db_session):
    org_id = uuid.uuid4()
    row, plaintext = await generate_organization_api_key(db_session, org_id, "key-1", ["chat:write"])
    await db_session.commit()

    await revoke_api_key(db_session, row.id)
    await db_session.commit()

    assert await verify_api_key(db_session, plaintext) is None


async def test_validate_scopes_rejects_unknown_scope():
    with pytest.raises(OrganizationAPIKeyError):
        validate_scopes(["not-a-real-scope"])


async def test_get_organization_from_api_key(db_session):
    org_id = uuid.uuid4()
    _row, plaintext = await generate_organization_api_key(db_session, org_id, "key-1", ["chat:write"])
    await db_session.commit()

    assert await get_organization_from_api_key(db_session, plaintext) == org_id


# --------------------------------------------------------------------- Endpoints


async def test_create_and_list_api_keys_endpoint(client, db_session, register_payload):
    """Validation criterion: la gestion des clés API fonctionne."""
    token, org_id, _api_key = await _make_org_with_api_key(client, db_session, register_payload, ["chat:write"])

    listing = await client.get(f"/organizations/{org_id}/api-keys", headers=_auth_header(token))
    assert listing.status_code == 200
    assert len(listing.json()) == 1
    assert listing.json()[0]["key_prefix"] == "pk_"


async def test_public_endpoint_rejects_missing_api_key(client):
    response = await client.post("/v1/embed", json={"text": "hello"})
    assert response.status_code == 422  # missing required header


async def test_public_endpoint_rejects_invalid_api_key(client):
    response = await client.post("/v1/embed", json={"text": "hello"}, headers=_api_key_header("pk_invalid"))
    assert response.status_code == 401


async def test_public_endpoint_rejects_wrong_scope(client, db_session, register_payload):
    """Validation criterion: sécurité -- les scopes sont respectés."""
    _token, _org_id, api_key = await _make_org_with_api_key(client, db_session, register_payload, ["chat:write"])
    response = await client.post("/v1/embed", json={"text": "hello"}, headers=_api_key_header(api_key))
    assert response.status_code == 403


async def test_public_knowledge_base_description_persists_and_is_returned(client, db_session):
    _key_row, api_key = await generate_organization_api_key(
        db_session, uuid.uuid4(), "knowledge-base-test", ["kb:read", "kb:write"],
    )
    await db_session.commit()

    created = await client.post(
        "/v1/knowledge-bases",
        json={"name": "Support", "description": "Customer support knowledge"},
        headers=_api_key_header(api_key),
    )
    assert created.status_code == 200
    assert created.json()["description"] == "Customer support knowledge"

    listing = await client.get("/v1/knowledge-bases", headers=_api_key_header(api_key))
    assert listing.status_code == 200
    assert listing.json()[0]["description"] == "Customer support knowledge"


# ------------------------------------------------------------------------- 9.1.1 Chat


async def test_public_chat_endpoint(monkeypatch, client, db_session, register_payload):
    """Validation criterion: l'endpoint public de chat fonctionne."""
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("Hello from the public API!")))
    monkeypatch.setattr("api.services.retrieval_pipeline.search_with_context", AsyncMock(return_value=[]))

    _token, _org_id, api_key = await _make_org_with_api_key(client, db_session, register_payload, ["chat:write"])
    response = await client.post("/v1/chat", json={"message": "Hi", "agent_id": "agent-1"}, headers=_api_key_header(api_key))

    assert response.status_code == 200
    assert response.json()["response"] == "Hello from the public API!"
    assert response.json()["conversation_id"]


async def test_public_chat_endpoint_is_rate_limited_per_organization(monkeypatch, client, db_session, register_payload):
    """Hardening Mission, Phase 2 -- REGRESSION for a real, confirmed
    audit gap: `api.services.public_api.handle_public_chat` (the single
    real choke point shared by the public /v1/chat API AND the
    embeddable widget) never applied any rate limit of its own. A
    per-API-KEY limit already existed separately
    (`api.services.organization_api_keys`, key "public_api:{key.id}") --
    this test deliberately lets THAT one pass through (`return` for any
    other key) so it isolates and proves the NEW, real, per-ORGANIZATION
    limit this Hardening Mission phase adds specifically, the one real
    protection the embeddable widget (no per-key auth at all) actually
    relies on. Mocked at the same clean boundary as
    tests/test_auth_api.py::test_login_email_scoped_rate_limit_alerts_the_real_account_owner
    (no real Redis needed)."""
    from fastapi import HTTPException, status

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("Hello!")))
    monkeypatch.setattr("api.services.retrieval_pipeline.search_with_context", AsyncMock(return_value=[]))

    _token, org_id, api_key = await _make_org_with_api_key(client, db_session, register_payload, ["chat:write"])
    expected_key = f"ratelimit:public_chat:org:{org_id}"

    calls = []

    async def _fake_enforce(key, max_attempts, window_seconds):
        calls.append(key)
        if key == expected_key:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts", headers={"Retry-After": "60"})

    monkeypatch.setattr("api.security.rate_limit.enforce_rate_limit", _fake_enforce)

    response = await client.post("/v1/chat", json={"message": "Hi", "agent_id": "agent-1"}, headers=_api_key_header(api_key))

    assert response.status_code == 429
    assert expected_key in calls


async def test_public_chat_endpoint_passes_a_real_user_context_for_policy_aware_retrieval(monkeypatch, client, db_session, register_payload):
    """Hardening Mission, Phase 2 -- REGRESSION for a real, confirmed
    audit gap: OPA/policy-aware retrieval was already correctly wired
    inside api.services.retrieval_pipeline.search, but no real HTTP
    caller (including this public API chat endpoint) ever built and
    passed a `user_context` at all. `handle_public_chat` now does."""
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("Hello from the public API!")))
    fake_search = AsyncMock(return_value=[])
    monkeypatch.setattr("api.services.retrieval_pipeline.search_with_context", fake_search)

    _token, org_id, api_key = await _make_org_with_api_key(client, db_session, register_payload, ["chat:write"])
    response = await client.post("/v1/chat", json={"message": "Hi", "agent_id": "agent-1"}, headers=_api_key_header(api_key))

    assert response.status_code == 200
    fake_search.assert_awaited_once()
    _, kwargs = fake_search.await_args
    assert kwargs["user_context"]["organization_id"] == str(org_id)
    assert kwargs["user_context"]["auth"] == "api_key"
    assert "created_by" in kwargs["user_context"]


async def test_public_chat_endpoint_reuses_existing_conversation(monkeypatch, client, db_session, register_payload):
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("First")))
    monkeypatch.setattr("api.services.retrieval_pipeline.search_with_context", AsyncMock(return_value=[]))

    _token, _org_id, api_key = await _make_org_with_api_key(client, db_session, register_payload, ["chat:write"])
    first = await client.post("/v1/chat", json={"message": "Hi", "agent_id": "agent-1"}, headers=_api_key_header(api_key))
    conversation_id = first.json()["conversation_id"]

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("Second")))
    second = await client.post(
        "/v1/chat", json={"message": "Again", "agent_id": "agent-1", "conversation_id": conversation_id}, headers=_api_key_header(api_key),
    )
    assert second.status_code == 200
    assert second.json()["conversation_id"] == conversation_id


# --------------------------------------------------------------------- 9.1.2 Documents


async def test_public_document_upload_endpoint(monkeypatch, client, db_session, register_payload):
    """Validation criterion: l'upload de document public fonctionne."""
    # Same real S3-mocking convention as tests/test_documents.py -- no
    # real bucket configured in this fast, local test run.
    monkeypatch.setattr(
        "api.security.documents.upload_document_file",
        lambda org_id, doc_id, filename, content, content_type: f"documents/{org_id}/{doc_id}/{filename}",
    )
    _token, _org_id, api_key = await _make_org_with_api_key(client, db_session, register_payload, ["documents:write"])
    files = {"file": ("test.txt", b"Hello, this is a real test document.", "text/plain")}
    response = await client.post("/v1/documents", files=files, headers=_api_key_header(api_key))

    assert response.status_code == 200
    assert response.json()["name"] == "test.txt"


# ---------------------------------------------------------------- 9.1.3 Knowledge bases


async def test_public_kb_creation_endpoint(client, db_session, register_payload):
    """Validation criterion: la création de KB publique fonctionne."""
    _token, _org_id, api_key = await _make_org_with_api_key(client, db_session, register_payload, ["kb:write"])
    response = await client.post("/v1/knowledge-bases", json={"name": "My KB"}, headers=_api_key_header(api_key))

    assert response.status_code == 200
    assert response.json()["name"] == "My KB"


# -------------------------------------------------------------------- 9.1.4 Conversations


async def test_public_conversations_list_endpoint(monkeypatch, client, db_session, register_payload):
    """Validation criterion: la liste des conversations publique fonctionne."""
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("Answer")))
    monkeypatch.setattr("api.services.retrieval_pipeline.search_with_context", AsyncMock(return_value=[]))

    _token, _org_id, api_key = await _make_org_with_api_key(client, db_session, register_payload, ["chat:write", "chat:read"])
    await client.post("/v1/chat", json={"message": "Hi", "agent_id": "agent-1"}, headers=_api_key_header(api_key))

    response = await client.get("/v1/conversations", headers=_api_key_header(api_key))
    assert response.status_code == 200
    assert response.json()["total"] == 1


# ------------------------------------------------------------------------ 9.1.5 Search


async def test_public_search_endpoint(monkeypatch, client, db_session, register_payload):
    """Validation criterion: la recherche publique fonctionne."""
    monkeypatch.setattr("api.services.retrieval_pipeline.search_with_context", AsyncMock(return_value=[{"text": "chunk", "score": 0.9}]))
    _token, _org_id, api_key = await _make_org_with_api_key(client, db_session, register_payload, ["search:read"])

    response = await client.post("/v1/search", json={"query": "test query"}, headers=_api_key_header(api_key))
    assert response.status_code == 200
    assert response.json()["total"] == 1


# --------------------------------------------------------------------- 9.1.6 Agents/run


async def test_public_agent_run_endpoint(monkeypatch, client, db_session, register_payload):
    """Validation criterion: l'exécution d'agent publique fonctionne."""
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("Run output")))
    _token, _org_id, api_key = await _make_org_with_api_key(client, db_session, register_payload, ["agents:run"])

    response = await client.post("/v1/agents/run", json={"agent_id": "agent-1", "input": "Do something"}, headers=_api_key_header(api_key))
    assert response.status_code == 200
    assert response.json()["output"] == "Run output"


async def test_public_agent_run_surfaces_failure(monkeypatch, client, db_session, register_payload):
    """Validation criterion: robustesse -- échec de l'agent."""
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(side_effect=litellm.exceptions.AuthenticationError(
        message="bad key", llm_provider="anthropic", model="claude",
    )))
    _token, _org_id, api_key = await _make_org_with_api_key(client, db_session, register_payload, ["agents:run"])

    response = await client.post("/v1/agents/run", json={"agent_id": "agent-1", "input": "Hi"}, headers=_api_key_header(api_key))
    assert response.status_code == 400


# ------------------------------------------------------------------------- 9.1.7 Usage


async def test_public_usage_endpoint(client, db_session, register_payload):
    """Validation criterion: l'endpoint d'usage public fonctionne."""
    _token, _org_id, api_key = await _make_org_with_api_key(client, db_session, register_payload, ["usage:read"])
    response = await client.get("/v1/usage?period=month", headers=_api_key_header(api_key))
    assert response.status_code == 200
    assert response.json()["period"] == "month"


# --------------------------------------------------------------------- 9.1.8 Analytics


async def test_public_analytics_endpoint(client, db_session, register_payload):
    """Validation criterion: l'endpoint d'analytics public fonctionne."""
    _token, _org_id, api_key = await _make_org_with_api_key(client, db_session, register_payload, ["analytics:read"])
    response = await client.get("/v1/analytics?period=week", headers=_api_key_header(api_key))
    assert response.status_code == 200
    assert "not yet implemented" in response.json()["summary"]


# ----------------------------------------------------------------------- 9.1.9 Embed


async def test_public_embed_endpoint(monkeypatch, client, db_session, register_payload):
    """Validation criterion: l'endpoint d'embedding public fonctionne."""
    monkeypatch.setattr("api.services.embedding_providers.get_embedding", AsyncMock(return_value=[0.1, 0.2, 0.3]))
    _token, _org_id, api_key = await _make_org_with_api_key(client, db_session, register_payload, ["embed:write"])

    response = await client.post("/v1/embed", json={"text": "hello world"}, headers=_api_key_header(api_key))
    assert response.status_code == 200
    assert response.json()["dimensions"] == 3


# ------------------------------------- Hardening Mission, §21/§24/§31/§7 (public API)


async def test_public_chat_with_stream_true_returns_real_server_sent_events(monkeypatch, client, db_session, register_payload):
    """`ChatRequest.stream` (and every SDK's `stream` argument) used to be
    silently IGNORED -- a full JSON body always came back. `stream=true`
    now returns a real `text/event-stream`, bound to the key's own
    organization, built from the same SSE generator the dashboard uses."""
    captured = {}

    async def _fake_stream(db, agent_id, message, **kwargs):
        captured.update(kwargs, agent_id=agent_id, message=message)
        yield 'event: start\ndata: {}\n\n'
        yield 'event: token\ndata: {"token": "Hel"}\n\n'
        yield 'event: done\ndata: {}\n\n'

    monkeypatch.setattr("api.services.streaming.stream_agent_response", _fake_stream)
    monkeypatch.setattr("api.services.retrieval_pipeline.search_with_context", AsyncMock(return_value=[]))
    _token, org_id, api_key = await _make_org_with_api_key(client, db_session, register_payload, ["chat:write"])

    response = await client.post("/v1/chat", json={"message": "Hi", "agent_id": "agent-1", "stream": True}, headers=_api_key_header(api_key))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert 'event: token' in response.text and '"Hel"' in response.text
    assert str(captured["organization_id"]) == org_id
    assert captured["message"] == "Hi"
    assert captured["conversation_id"] is not None


async def test_public_chat_stream_true_still_refuses_with_a_real_http_429_before_any_stream_starts(monkeypatch, client, db_session, register_payload):
    from fastapi import HTTPException, status

    async def _boom(key, max_attempts, window_seconds):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts", headers={"Retry-After": "60"})

    monkeypatch.setattr("api.security.rate_limit.enforce_rate_limit", _boom)
    _token, _org_id, api_key = await _make_org_with_api_key(client, db_session, register_payload, ["chat:write"])

    response = await client.post("/v1/chat", json={"message": "Hi", "agent_id": "agent-1", "stream": True}, headers=_api_key_header(api_key))

    assert response.status_code == 429
    assert not response.headers["content-type"].startswith("text/event-stream")


async def test_public_chat_and_agent_run_refuse_another_organizations_real_agent(monkeypatch, client, db_session, register_payload):
    """Multi-tenancy: `agent_id` is a free string from the request body;
    an org-A key must never drive org B's real agent (its prompt/tools/KB)."""
    from api.models.agent import Agent
    from api.models.organization import Organization

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_response("should never be called")))
    monkeypatch.setattr("api.services.retrieval_pipeline.search_with_context", AsyncMock(return_value=[]))
    _token, _org_id, api_key = await _make_org_with_api_key(client, db_session, register_payload, ["chat:write", "agents:run"])
    other_org = Organization(name="Other", slug=f"other-{uuid.uuid4().hex[:8]}")
    db_session.add(other_org)
    await db_session.flush()
    foreign_agent = Agent(organization_id=other_org.id, name="secret", system_prompt="TOP SECRET", model_config_json={})
    db_session.add(foreign_agent)
    await db_session.flush()
    foreign_agent_id = foreign_agent.id  # read before commit: commit expires the instance, and a lazy refresh is not allowed in async
    await db_session.commit()

    chat = await client.post("/v1/chat", json={"message": "Hi", "agent_id": str(foreign_agent_id)}, headers=_api_key_header(api_key))
    run = await client.post("/v1/agents/run", json={"agent_id": str(foreign_agent_id), "input": "Hi"}, headers=_api_key_header(api_key))

    assert chat.status_code == 400 and "Agent not found" in chat.text
    assert run.status_code == 400 and "Agent not found" in run.text
    litellm.acompletion.assert_not_awaited()


async def test_public_conversations_list_reports_a_real_total_and_each_conversations_last_message(client, db_session, register_payload):
    import datetime as dt

    from sqlalchemy import select

    from api.models.conversation import Conversation, ConversationMessage
    from api.models.user import User

    _token, org_id, api_key = await _make_org_with_api_key(client, db_session, register_payload, ["chat:read"])
    user = await db_session.scalar(select(User).where(User.email == register_payload["email"]))
    base = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    conversations = []
    for i in range(3):
        conversation = Conversation(agent_id="agent-1", user_id=user.id, organization_id=uuid.UUID(org_id), title=f"c{i}")
        db_session.add(conversation)
        await db_session.flush()
        for j, text in enumerate(["first", "second", f"LAST-{i}"]):
            db_session.add(ConversationMessage(conversation_id=conversation.id, role="user", content=text, created_at=base + dt.timedelta(minutes=j)))
        conversations.append(conversation)
    await db_session.commit()

    response = await client.get("/v1/conversations", params={"limit": 2}, headers=_api_key_header(api_key))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3 and len(body["items"]) == 2
    assert all(item["last_message_preview"].startswith("LAST-") for item in body["items"])

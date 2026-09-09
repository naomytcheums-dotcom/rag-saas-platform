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

"""Phase 5, Étape 11 -- real, per-LIVE-query retrieval diagnostics
(api/models/retrieval_diagnostic.py). Service-layer tests exercise
`record_retrieval_diagnostic` directly; endpoint tests exercise the
real, org-scoped read surface."""

import uuid
from unittest.mock import AsyncMock

import litellm
import pytest
from litellm.types.utils import Choices, Message, ModelResponse
from sqlalchemy import select

from api.config import settings
from api.models.organization import Organization, OrganizationMember, OrganizationRole
from api.models.retrieval_diagnostic import RetrievalDiagnostic
from api.models.user import User
from api.services.generation import generate_response
from api.services.retrieval_pipeline import record_retrieval_diagnostic


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _create_org(client, access_token: str, name: str) -> dict:
    return (await client.post("/organizations", json={"name": name}, headers=_auth_header(access_token))).json()


async def test_record_retrieval_diagnostic_persists_a_real_row(db_session):
    org = Organization(name="Acme", slug=f"acme-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()

    results = [{"chunk_id": "c1", "document_id": "d1", "score": 0.9}, {"chunk_id": "c2", "document_id": "d2", "score": 0.7}]
    diag = await record_retrieval_diagnostic(db_session, org.id, "what is RAG?", "hybrid_reranked", results, 123)
    await db_session.commit()

    row = await db_session.get(RetrievalDiagnostic, diag.id)
    assert row.organization_id == org.id
    assert row.query == "what is RAG?"
    assert row.strategy == "hybrid_reranked"
    assert row.result_count == 2
    assert row.latency_ms == 123
    assert row.final_chunks == [{"chunk_id": "c1", "document_id": "d1", "score": 0.9}, {"chunk_id": "c2", "document_id": "d2", "score": 0.7}]


async def test_record_retrieval_diagnostic_never_stores_full_chunk_text(db_session):
    """Validation criterion: le diagnostic ne duplique pas le contenu réel des chunks."""
    org = Organization(name="Acme", slug=f"acme-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()

    results = [{"chunk_id": "c1", "document_id": "d1", "score": 0.9, "content": "some real document text that should not be duplicated here"}]
    diag = await record_retrieval_diagnostic(db_session, org.id, "q", "hybrid", results, 10)
    await db_session.commit()

    assert "content" not in diag.final_chunks[0]


async def test_generate_response_records_a_real_diagnostic(monkeypatch, db_session):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-test")
    org = Organization(name="Acme", slug=f"acme-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()

    chunk = {
        "chunk_id": str(uuid.uuid4()), "document_id": str(uuid.uuid4()), "content": "The sky scatters blue light.",
        "score": 0.9, "document_name": "physics.pdf", "file_type": "application/pdf",
    }
    monkeypatch.setattr("api.services.generation.search_with_context", AsyncMock(return_value=[chunk]))

    def _fake_completion(*args, **kwargs):
        message = Message(content="The sky is blue.", role="assistant")
        return ModelResponse(choices=[Choices(message=message, index=0, finish_reason="stop")])

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(side_effect=_fake_completion))

    await generate_response(db_session, org.id, "why is the sky blue?")
    await db_session.commit()

    diagnostics = (await db_session.scalars(select(RetrievalDiagnostic).where(RetrievalDiagnostic.organization_id == org.id))).all()
    assert len(diagnostics) == 1
    assert diagnostics[0].query == "why is the sky blue?"
    assert diagnostics[0].result_count == 1


async def test_list_retrieval_diagnostics_endpoint_is_org_scoped(client, db_session, register_payload):
    """Validation criterion: isolation multi-tenant -- pas de fuite cross-tenant."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_a = await _create_org(client, owner_token, "Org A")
    org_b = await _create_org(client, owner_token, "Org B")

    await record_retrieval_diagnostic(db_session, uuid.UUID(org_a["id"]), "q-a", "hybrid", [], 5)
    await record_retrieval_diagnostic(db_session, uuid.UUID(org_b["id"]), "q-b", "hybrid", [], 5)
    await db_session.commit()

    response = await client.get(f"/organizations/{org_a['id']}/retrieval-diagnostics", headers=_auth_header(owner_token))
    assert response.status_code == 200
    queries = [d["query"] for d in response.json()]
    assert queries == ["q-a"]


async def test_list_retrieval_diagnostics_requires_membership(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Acme")
    stranger_token, stranger = await _register(client, db_session, "stranger@example.com")

    response = await client.get(f"/organizations/{org['id']}/retrieval-diagnostics", headers=_auth_header(stranger_token))
    assert response.status_code == 404

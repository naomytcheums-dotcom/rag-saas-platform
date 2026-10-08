"""Hardening Mission, Phase 1 -- real HTTP test for
`GET /organizations/{org_id}/embeddings/status`, the explicit,
user-facing answer the mission's point 5 demands instead of an
organization silently losing recall on its own older documents after an
`embedding_model` change. No real embedding model is loaded (fake,
literal float lists) -- this endpoint is about counting/comparing
`embedding_model` strings, not embedding semantics."""

import uuid

from api.models.document import Document, DocumentChunk, DocumentStatus
from api.security.organization_settings import DEFAULT_SETTINGS


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _register(client, email: str, password: str = "correct-horse-battery-staple"):
    response = await client.post("/auth/register", json={"email": email, "password": password, "accept_terms": True})
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


async def _create_org(client, token: str, name: str) -> dict:
    response = await client.post("/organizations", json={"name": name}, headers=_auth_header(token))
    assert response.status_code == 201, response.text
    return response.json()


async def test_embedding_staleness_route_reports_no_reindex_needed_when_everything_is_current(client, db_session):
    token = await _register(client, "owner-fresh@example.com")
    org = await _create_org(client, token, "Fresh Org")
    current_model = DEFAULT_SETTINGS["embedding_model"]

    document = Document(
        organization_id=uuid.UUID(org["id"]), name="doc.pdf", file_key="documents/a/doc.pdf",
        file_size=10, file_type="application/pdf", status=DocumentStatus.completed.value,
    )
    db_session.add(document)
    await db_session.flush()
    db_session.add(DocumentChunk(
        document_id=document.id, organization_id=uuid.UUID(org["id"]), content="hello",
        embedding=[0.1, 0.2, 0.3], embedding_model=current_model, embedding_dim=3,
    ))
    await db_session.commit()

    response = await client.get(f"/organizations/{org['id']}/embeddings/status", headers=_auth_header(token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["current_embedding_model"] == current_model
    assert body["current_model_chunks"] == 1
    assert body["stale_chunks"] == 0
    assert body["legacy_chunks"] == 0
    assert body["reindex_recommended"] is False


async def test_embedding_staleness_route_recommends_reindex_for_stale_and_legacy_chunks(client, db_session):
    token = await _register(client, "owner-stale@example.com")
    org = await _create_org(client, token, "Stale Org")
    current_model = DEFAULT_SETTINGS["embedding_model"]

    document = Document(
        organization_id=uuid.UUID(org["id"]), name="doc.pdf", file_key="documents/b/doc.pdf",
        file_size=10, file_type="application/pdf", status=DocumentStatus.completed.value,
    )
    db_session.add(document)
    await db_session.flush()
    db_session.add_all([
        DocumentChunk(
            document_id=document.id, organization_id=uuid.UUID(org["id"]), content="current",
            embedding=[0.1, 0.2, 0.3], embedding_model=current_model, embedding_dim=3,
        ),
        DocumentChunk(
            document_id=document.id, organization_id=uuid.UUID(org["id"]), content="stale",
            embedding=[0.1] * 768, embedding_model="sentence-transformers/all-mpnet-base-v2", embedding_dim=768,
        ),
        DocumentChunk(
            document_id=document.id, organization_id=uuid.UUID(org["id"]), content="legacy, predates provenance tracking",
            embedding=[0.1, 0.2, 0.3], embedding_model=None, embedding_dim=None,
        ),
    ])
    await db_session.commit()

    response = await client.get(f"/organizations/{org['id']}/embeddings/status", headers=_auth_header(token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["current_model_chunks"] == 1
    assert body["stale_chunks"] == 1
    assert body["legacy_chunks"] == 1
    assert body["stale_models"] == {"sentence-transformers/all-mpnet-base-v2": 1}
    assert body["reindex_recommended"] is True


async def test_embedding_staleness_route_requires_admin_permission(client, db_session):
    from sqlalchemy import select

    from api.models.organization import OrganizationMember, OrganizationRole
    from api.models.user import User

    owner_token = await _register(client, "owner-perm@example.com")
    org = await _create_org(client, owner_token, "Perm Org")

    viewer_token = await _register(client, "viewer-perm@example.com")
    viewer = await db_session.scalar(select(User).where(User.email == "viewer-perm@example.com"))
    db_session.add(OrganizationMember(organization_id=uuid.UUID(org["id"]), user_id=viewer.id, role=OrganizationRole.viewer))
    await db_session.commit()

    response = await client.get(f"/organizations/{org['id']}/embeddings/status", headers=_auth_header(viewer_token))
    assert response.status_code == 403

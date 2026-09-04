"""Partie 3.3.4-3.3.6 -- tests for POST /organizations/{org_id}/search
(api/routers/search.py). Real embeddings, real end-to-end HTTP flow
through api/services/retrieval_pipeline.py -- no mocking, matching
this codebase's own established real-infrastructure testing
precedent."""

import uuid

from sqlalchemy import select

from api.models.document import Document, DocumentChunk, DocumentStatus
from api.models.organization import OrganizationMember, OrganizationRole
from api.models.user import User
from api.security.documents import generate_embeddings

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _create_org(client, access_token: str, name: str) -> dict:
    return (await client.post("/organizations", json={"name": name}, headers=_auth_header(access_token))).json()


async def _add_member(db_session, org_id, user_id, role: OrganizationRole):
    org_id = uuid.UUID(org_id) if isinstance(org_id, str) else org_id
    db_session.add(OrganizationMember(organization_id=org_id, user_id=user_id, role=role))
    await db_session.commit()


async def _add_document_with_chunks(db_session, org_id, texts, name="doc.pdf"):
    org_id = uuid.UUID(org_id) if isinstance(org_id, str) else org_id
    document = Document(
        organization_id=org_id, name=name, file_key=f"documents/{uuid.uuid4()}/{name}",
        file_size=100, file_type="application/pdf", status=DocumentStatus.completed.value,
    )
    db_session.add(document)
    await db_session.flush()
    embeddings = generate_embeddings(texts, EMBEDDING_MODEL)
    for text, embedding in zip(texts, embeddings):
        db_session.add(DocumentChunk(document_id=document.id, organization_id=org_id, content=text, embedding=embedding))
    await db_session.commit()
    return document


async def test_member_can_search_and_gets_real_results(client, db_session, register_payload):
    """Validation criterion: la recherche fonctionne pour une
    organisation."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Search Test Org")
    await _add_document_with_chunks(db_session, org["id"], ["Our refund policy allows returns within 30 days."])

    response = await client.post(
        f"/organizations/{org['id']}/search", json={"query": "refund policy", "strategy": "vector_only"},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["strategy"] == "vector_only"
    assert len(body["results"]) == 1
    assert "refund policy" in body["results"][0]["content"]
    assert body["results"][0]["context"]["document_name"] == "doc.pdf"


async def test_viewer_can_search(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Search Viewer Org")
    await _add_document_with_chunks(db_session, org["id"], ["Real content viewers should be able to find."])

    viewer_token, viewer = await _register(client, db_session, f"viewer-{uuid.uuid4().hex[:8]}@example.com")
    await _add_member(db_session, org["id"], viewer.id, OrganizationRole.viewer)

    response = await client.post(
        f"/organizations/{org['id']}/search", json={"query": "content viewers", "strategy": "vector_only"},
        headers=_auth_header(viewer_token),
    )
    assert response.status_code == 200
    assert len(response.json()["results"]) == 1


async def test_non_member_cannot_search(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Search Non Member Org")

    outsider_token, outsider = await _register(client, db_session, f"outsider-{uuid.uuid4().hex[:8]}@example.com")
    response = await client.post(
        f"/organizations/{org['id']}/search", json={"query": "anything"}, headers=_auth_header(outsider_token),
    )
    # require_org_member returns 404, not 403, for a non-member --
    # collapsing "no such org" and "not a member" into one response so
    # a caller can't probe which organization ids exist (same
    # anti-enumeration reasoning as DELETE /sessions/{id}).
    assert response.status_code == 404


async def test_search_never_returns_another_organizations_results(client, db_session, register_payload):
    """Validation criterion: la recherche ne retourne pas les chunks
    d'une autre organisation -- the most important real check."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_a = await _create_org(client, owner_token, "Search Isolation A")
    org_b = await _create_org(client, owner_token, "Search Isolation B")
    await _add_document_with_chunks(db_session, org_a["id"], ["Confidential org A onboarding steps."])
    await _add_document_with_chunks(db_session, org_b["id"], ["Confidential org B onboarding steps."])

    response = await client.post(
        f"/organizations/{org_a['id']}/search", json={"query": "onboarding steps", "strategy": "vector_only"},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 1
    assert "org A" in results[0]["content"]


async def test_search_rejects_an_invalid_strategy(client, db_session, register_payload):
    """Validation criterion: robustesse/tests -- une valeur invalide
    est rejetée par le schéma avant même d'atteindre le pipeline."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Search Invalid Strategy Org")

    response = await client.post(
        f"/organizations/{org['id']}/search", json={"query": "anything", "strategy": "made_up_strategy"},
        headers=_auth_header(owner_token),
    )
    assert response.status_code == 422


async def test_search_rejects_an_empty_query(client, db_session, register_payload):
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Search Empty Query Org")

    response = await client.post(f"/organizations/{org['id']}/search", json={"query": ""}, headers=_auth_header(owner_token))
    assert response.status_code == 422


async def test_search_uses_the_real_organization_configured_strategy_by_default(client, db_session, register_payload):
    """Validation criterion: les paramètres de config sont appliqués --
    no strategy given in the request, so the organization's own
    configured retrieval_strategy applies."""
    owner_token, owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org = await _create_org(client, owner_token, "Search Config Applied Org")
    await client.patch(
        f"/organizations/{org['id']}/settings", json={"retrieval_strategy": "bm25_only"}, headers=_auth_header(owner_token),
    )
    await _add_document_with_chunks(db_session, org["id"], ["A very specific keyword abracadabra123 appears here."])

    response = await client.post(
        f"/organizations/{org['id']}/search", json={"query": "abracadabra123"}, headers=_auth_header(owner_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["strategy"] == "bm25_only"
    assert len(body["results"]) == 1

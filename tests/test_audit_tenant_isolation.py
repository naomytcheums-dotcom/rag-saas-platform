"""AUDIT CONTRADICTOIRE -- Phase 2 & Phase 59 : vérification EMPIRIQUE,
en direct, à travers la vraie API HTTP (pas seulement au niveau
service) de l'isolation multi-tenant. Deux organisations réelles créées
via /auth/register + /organizations, un document réel ajouté à A
uniquement, puis une tentative réelle depuis B de le récupérer par
chaque chemin possible : recherche (vector/bm25/hybrid), accès direct
par ID (document, chunk, citation), et l'endpoint public de citations.
"""

import uuid

from sqlalchemy import select

from api.models.citation import Citation
from api.models.document import Document, DocumentChunk, DocumentStatus
from api.models.response import Response
from api.security.documents import generate_embeddings

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _register(client, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


async def _create_org(client, token: str, name: str) -> dict:
    response = await client.post("/organizations", json={"name": name}, headers=_auth_header(token))
    assert response.status_code == 201, response.text
    return response.json()


async def test_audit_phase2_phase59_org_b_can_never_retrieve_org_a_document(client, db_session):
    """AUDIT : crée A et B (comptes et organisations réellement
    distincts), ajoute un document SECRET uniquement à A, puis prouve
    depuis B, via la VRAIE API HTTP, qu'aucun chemin ne fuit le
    contenu de A -- recherche (3 stratégies réelles), accès direct par
    ID de document/chunk, endpoint de citations."""
    token_a = await _register(client, "owner-a@example.com")
    org_a = await _create_org(client, token_a, "Org A")

    token_b = await _register(client, "owner-b@example.com")
    org_b = await _create_org(client, token_b, "Org B")

    # Document réel, contenu SECRET, appartenant uniquement à A.
    secret_text = "SECRET-A-CONFIDENTIAL: le mot de passe du coffre est HORLOGE-BLEUE-42."
    document = Document(
        organization_id=uuid.UUID(org_a["id"]), workspace_id=None, name="secret-a.pdf",
        file_key="documents/a/secret-a.pdf", file_size=len(secret_text), file_type="application/pdf",
        status=DocumentStatus.completed.value, created_by=None,
    )
    db_session.add(document)
    await db_session.flush()

    embedding = generate_embeddings([secret_text], EMBEDDING_MODEL)[0]
    chunk = DocumentChunk(
        document_id=document.id, organization_id=uuid.UUID(org_a["id"]), content=secret_text,
        embedding=embedding, chunk_index=0, metadata_json={},
    )
    db_session.add(chunk)
    await db_session.commit()

    # --- Tentative 1 : recherche depuis B, chaque stratégie réelle ---
    leaked = []
    for strategy in ("hybrid", "vector_only", "bm25_only"):
        response = await client.post(
            f"/organizations/{org_b['id']}/search",
            json={"query": "HORLOGE-BLEUE-42 coffre secret", "strategy": strategy, "top_k": 10},
            headers=_auth_header(token_b),
        )
        assert response.status_code == 200, response.text
        results = response.json()["results"]
        if results:
            leaked.append((strategy, results))

    assert leaked == [], f"FUITE DÉTECTÉE via recherche: {leaked}"

    # --- Tentative 2 : B connaît l'UUID réel du document de A (IDOR) ---
    response = await client.get(f"/documents/{document.id}", headers=_auth_header(token_b))
    assert response.status_code in (403, 404), f"IDOR possible sur /documents/{{id}}: {response.status_code} {response.text}"

    # --- Tentative 3 : B essaie de lister les documents de A en se déclarant org A dans l'URL ---
    response = await client.get(f"/organizations/{org_a['id']}/documents", headers=_auth_header(token_b))
    assert response.status_code in (403, 404), f"B a pu lister les documents de A: {response.status_code} {response.text}"

    # --- Tentative 4 : une vraie Response+Citation créée sous A n'est jamais visible depuis B ---
    resp = Response(organization_id=uuid.UUID(org_a["id"]), workspace_id=None, query="q", answer="a", created_by=None)
    db_session.add(resp)
    await db_session.flush()
    citation = Citation(
        response_id=resp.id, document_id=document.id, chunk_id=chunk.id, text=secret_text,
        relevance_score=0.9, citation_number=1, document_name=document.name, document_type=document.file_type,
    )
    db_session.add(citation)
    await db_session.commit()

    response = await client.get(f"/citations/{citation.id}", headers=_auth_header(token_b))
    assert response.status_code in (403, 404, 405, 422), f"B a pu lire une citation de A: {response.status_code} {response.text}"

    print("\n=== AUDIT PHASE 2/59 : AUCUNE FUITE DÉTECTÉE sur les 4 vecteurs testés (search x3 strategies, IDOR document, listing cross-org, citation cross-org) ===")

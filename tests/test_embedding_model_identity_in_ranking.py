"""E2E finding 2026-10-12: two embedding models with the SAME dimension were compared as if they shared one vector space. Pure-Python vectors
(no model download): the chunk stamped with another model must never be ranked against a query embedded by this organization's model."""

import uuid

from api.models.document import Document, DocumentChunk, DocumentStatus
from api.models.organization import Organization
from api.services.retrieval_pipeline import fetch_organization_chunks, rank_chunks_by_embedding

MODEL_A = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_B = "sentence-transformers/multi-qa-MiniLM-L6-cos-v1"  # also 384 dimensions


async def _org_with_chunks(db_session):
    org = Organization(name="Identity org", slug=f"identity-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    doc = Document(organization_id=org.id, name="d.txt", file_key="documents/x/d.txt", file_size=10, file_type="text/plain", status=DocumentStatus.completed.value)
    db_session.add(doc)
    await db_session.flush()
    same_direction = [1.0] + [0.0] * 383
    for text, model in (("chunk embedded by model A", MODEL_A), ("chunk embedded by model B", MODEL_B), ("legacy chunk, model unknown", None)):
        db_session.add(DocumentChunk(document_id=doc.id, organization_id=org.id, content=text, embedding=same_direction, embedding_model=model, embedding_dim=384))
    await db_session.commit()
    return org.id, same_direction


async def test_ranking_ignores_chunks_embedded_by_another_model_of_the_same_dimension(db_session):
    org_id, vector = await _org_with_chunks(db_session)

    results = await rank_chunks_by_embedding(db_session, org_id, vector, top_k=10, embedding_model=MODEL_A)

    contents = {r["content"] for r in results}
    assert "chunk embedded by model A" in contents
    assert "chunk embedded by model B" not in contents
    assert "legacy chunk, model unknown" in contents  # no stamp: origin unknown, stays comparable


async def test_without_a_model_the_old_behaviour_is_unchanged(db_session):
    org_id, vector = await _org_with_chunks(db_session)

    results = await rank_chunks_by_embedding(db_session, org_id, vector, top_k=10)

    assert len(results) == 3


async def test_fetch_filters_by_model_too(db_session):
    org_id, _ = await _org_with_chunks(db_session)

    chunks = await fetch_organization_chunks(db_session, org_id, embedding_model=MODEL_B)

    assert {c["content"] for c in chunks} == {"chunk embedded by model B", "legacy chunk, model unknown"}

"""Hardening Mission, Phase 1 -- regression tests for a real,
externally-audited, reproduced crash: `api.services.retrieval_pipeline`
used to raise `ValueError: setting an array element with a sequence`
whenever an organization's chunks mixed embeddings of different
dimensions (the real, common case of an org changing its configured
`embedding_model` without every existing chunk being reindexed yet).

No real embedding model is loaded here on purpose (fake, literal float
lists) -- this bug is about array SHAPE, not embedding semantics, so a
real model would only add real RAM/CPU cost for zero extra coverage."""

import uuid

from api.models.document import Document, DocumentChunk, DocumentStatus
from api.models.organization import Organization
from api.services.retrieval_pipeline import _split_chunks_by_dimension, cosine_similarities, rank_chunks_by_embedding


async def _make_org_with_document(db_session):
    org = Organization(name="Dim Org", slug=f"dim-org-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    document = Document(
        organization_id=org.id, name="doc.pdf", file_key=f"documents/{uuid.uuid4()}/doc.pdf",
        file_size=100, file_type="application/pdf", status=DocumentStatus.completed.value,
    )
    db_session.add(document)
    await db_session.flush()
    return org, document


def test_cosine_similarities_still_crashes_on_a_ragged_input_directly():
    """Proves the ORIGINAL bug is real at the numpy level (documents the
    failure this module's own real fix routes around, rather than
    silently hiding what the underlying limitation actually is)."""
    import numpy as np
    import pytest

    with pytest.raises(ValueError):
        cosine_similarities([1.0, 0.0, 0.0], [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]])


def test_split_chunks_by_dimension_excludes_only_the_mismatched_ones():
    chunks = [
        {"chunk_id": "a", "embedding": [1.0, 0.0, 0.0]},
        {"chunk_id": "b", "embedding": [0.0, 1.0, 0.0, 0.0]},
        {"chunk_id": "c", "embedding": [0.9, 0.1, 0.0]},
    ]
    comparable, excluded = _split_chunks_by_dimension([1.0, 0.0, 0.0], chunks)
    assert excluded == 1
    assert [c["chunk_id"] for c in comparable] == ["a", "c"]


async def test_rank_chunks_by_embedding_never_crashes_on_a_real_mixed_dimension_organization(db_session):
    """AUDIT REGRESSION -- an organization that changed `embedding_model`
    has real chunks of two different dimensions in the SAME real table
    row set. A real search against it used to raise instead of
    returning real, correct results for the still-comparable chunks."""
    org, document = await _make_org_with_document(db_session)

    # A real, old chunk embedded under a since-replaced 384-dim model.
    db_session.add(DocumentChunk(
        document_id=document.id, organization_id=org.id, content="old dimension chunk",
        embedding=[0.0] * 384, embedding_model="sentence-transformers/all-MiniLM-L6-v2", embedding_dim=384,
    ))
    # A real, newer chunk embedded under a since-changed 768-dim model --
    # the SAME dimension the query below uses, so it must be the one
    # (and only) real match returned.
    target_embedding = [0.1] * 767 + [0.9]
    db_session.add(DocumentChunk(
        document_id=document.id, organization_id=org.id, content="new dimension chunk",
        embedding=target_embedding, embedding_model="sentence-transformers/all-mpnet-base-v2", embedding_dim=768,
    ))
    await db_session.commit()

    results = await rank_chunks_by_embedding(db_session, org.id, target_embedding, top_k=10)

    assert len(results) == 1, "the 384-dim chunk must be excluded, never crash the whole ranking pass"
    assert results[0]["content"] == "new dimension chunk"
    assert results[0]["score"] > 0.99

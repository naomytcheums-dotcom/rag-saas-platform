"""Hardening Mission, §7 -- behaviours behind the measured retrieval speed-ups
(scripts/retrieval_benchmark.py, A/B on 5,000 chunks): the keyword leg no longer
loads every chunk's embedding (2.04 s -> 0.19 s), and the CPU-bound ranking runs
off the event loop. Real DB session, real rows, deterministic random embeddings
(no embedding model needed)."""

import asyncio
import time
import uuid

import numpy as np
from sqlalchemy import select

from api.config import settings as app_settings
from api.models.document import Document, DocumentChunk, DocumentStatus
from api.models.organization import Organization
from api.services import retrieval_pipeline as rp

DIM = 8


async def _org_with_chunks(db_session, texts: list[str], name="Perf Org") -> tuple[uuid.UUID, list[str]]:
    org = Organization(name=name, slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    document = Document(
        organization_id=org.id, name="doc.pdf", file_key=f"documents/{uuid.uuid4()}/doc.pdf", file_size=1,
        file_type="application/pdf", status=DocumentStatus.completed.value,
    )
    db_session.add(document)
    await db_session.flush()
    rng = np.random.default_rng(3)
    ids = []
    for index, text in enumerate(texts):
        vector = rng.standard_normal(DIM)
        chunk = DocumentChunk(
            document_id=document.id, organization_id=org.id, content=text, embedding=(vector / np.linalg.norm(vector)).tolist(),
            embedding_dim=DIM, chunk_index=index,
        )
        db_session.add(chunk)
        await db_session.flush()
        ids.append(str(chunk.id))
    await db_session.commit()
    return org.id, ids


async def test_the_keyword_fetch_skips_embeddings_but_returns_the_same_chunks_and_fields(db_session):
    org_id, ids = await _org_with_chunks(db_session, ["alpha beta", "gamma delta", "epsilon zeta"])

    with_embeddings = await rp.fetch_organization_chunks(db_session, org_id)
    without = await rp.fetch_organization_chunks(db_session, org_id, with_embeddings=False)

    assert sorted(c["chunk_id"] for c in with_embeddings) == sorted(ids) == sorted(c["chunk_id"] for c in without)
    assert all(isinstance(c["embedding"], list) and len(c["embedding"]) == DIM for c in with_embeddings)
    assert all(c["embedding"] is None for c in without)
    by_id = {c["chunk_id"]: c for c in with_embeddings}
    for chunk in without:
        twin = by_id[chunk["chunk_id"]]
        for field in ("content", "document_id", "document_name", "file_type", "chunk_index", "source_url", "metadata_json", "media_asset_id"):
            assert chunk[field] == twin[field], field


async def test_the_keyword_fetch_keeps_the_organization_isolation(db_session):
    org_a, ids_a = await _org_with_chunks(db_session, ["secret alpha"], name="Org A")
    org_b, ids_b = await _org_with_chunks(db_session, ["secret beta"], name="Org B")

    seen_by_a = await rp.fetch_organization_chunks(db_session, org_a, with_embeddings=False)

    assert [c["chunk_id"] for c in seen_by_a] == ids_a
    assert not set(ids_b) & {c["chunk_id"] for c in seen_by_a}


async def test_bm25_search_still_ranks_correctly_without_loading_embeddings(db_session):
    org_id, ids = await _org_with_chunks(db_session, ["the cat sat on the mat", "quantum chromodynamics lecture notes", "grocery list eggs milk bread"])

    results = await rp.bm25_search(db_session, org_id, "quantum chromodynamics", top_k=2)

    assert results[0]["chunk_id"] == ids[1]
    assert results[0]["score"] > 0 and results[0]["embedding"] is None


async def test_bm25_cache_reuses_filtered_index_and_matches_uncached_results(db_session, monkeypatch):
    org = Organization(name="BM25 Cache Filter Org", slug=f"bm25-cache-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()
    docs = []
    chunks = []
    for name, label, text in (
        ("one.pdf", "one", "cedar cedar cedar report"),
        ("two.pdf", "two", "cedar report elsewhere"),
    ):
        document = Document(
            organization_id=org.id, name=name, file_key=f"documents/{uuid.uuid4()}/{name}", file_size=1,
            file_type="application/pdf", status=DocumentStatus.completed.value,
        )
        db_session.add(document)
        await db_session.flush()
        chunk = DocumentChunk(
            document_id=document.id, organization_id=org.id, content=text,
            metadata_json={"group": label}, embedding=[1.0] * DIM,
        )
        db_session.add(chunk)
        docs.append(document)
        chunks.append(chunk)
    await db_session.commit()

    original_fetch = rp.fetch_organization_chunks
    fetch_count = 0

    async def counted_fetch(*args, **kwargs):
        nonlocal fetch_count
        fetch_count += 1
        return await original_fetch(*args, **kwargs)

    monkeypatch.setattr(rp, "fetch_organization_chunks", counted_fetch)
    monkeypatch.setattr(app_settings, "METADATA_FILTERING_ENABLED", True)
    monkeypatch.setattr(app_settings, "BM25_INDEX_CACHE_ENABLED", True)
    filters = {"group": "one"}
    first = await rp.bm25_search(db_session, org.id, "cedar report", top_k=5, metadata_filters=filters)
    second = await rp.bm25_search(db_session, org.id, "cedar report", top_k=5, metadata_filters=filters)
    assert first == second
    assert [row["chunk_id"] for row in first] == [str(chunks[0].id)]
    assert fetch_count == 1

    by_document = await rp.bm25_search(db_session, org.id, "cedar report", top_k=5, document_ids=[docs[1].id])
    assert [row["chunk_id"] for row in by_document] == [str(chunks[1].id)]
    assert fetch_count == 2

    monkeypatch.setattr(app_settings, "BM25_INDEX_CACHE_ENABLED", False)
    uncached = await rp.bm25_search(db_session, org.id, "cedar report", top_k=5, metadata_filters=filters)
    assert uncached == first
    assert fetch_count == 3


async def test_bm25_cache_invalidates_after_chunk_insert_and_delete(db_session, monkeypatch):
    org_id, _ = await _org_with_chunks(db_session, [])
    monkeypatch.setattr(app_settings, "BM25_INDEX_CACHE_ENABLED", True)
    assert await rp.bm25_search(db_session, org_id, "freshkeyword", top_k=5) == []

    document = Document(
        organization_id=org_id, name="fresh.pdf", file_key=f"documents/{uuid.uuid4()}/fresh.pdf", file_size=1,
        file_type="application/pdf", status=DocumentStatus.completed.value,
    )
    db_session.add(document)
    await db_session.flush()
    chunk = DocumentChunk(
        document_id=document.id, organization_id=org_id, content="freshkeyword appears here", embedding=[1.0] * DIM,
    )
    db_session.add(chunk)
    await db_session.commit()
    assert [row["chunk_id"] for row in await rp.bm25_search(db_session, org_id, "freshkeyword", top_k=5)] == [str(chunk.id)]

    await db_session.delete(chunk)
    await db_session.commit()
    assert await rp.bm25_search(db_session, org_id, "freshkeyword", top_k=5) == []


async def test_bm25_cache_invalidates_when_document_is_soft_deleted(db_session, monkeypatch):
    org_id, chunk_ids = await _org_with_chunks(db_session, ["softgone cedar content"])
    monkeypatch.setattr(app_settings, "BM25_INDEX_CACHE_ENABLED", True)
    assert [row["chunk_id"] for row in await rp.bm25_search(db_session, org_id, "softgone", top_k=5)] == chunk_ids

    document = await db_session.scalar(select(Document).where(Document.organization_id == org_id))
    document.deleted_at = document.updated_at or __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    await db_session.commit()

    assert await rp.bm25_search(db_session, org_id, "softgone", top_k=5) == []


async def test_bm25_cache_keeps_organization_indexes_isolated(db_session, monkeypatch):
    org_a, ids_a = await _org_with_chunks(db_session, ["tenantonly willow phrase"], name="BM25 Cache A")
    org_b, ids_b = await _org_with_chunks(db_session, ["tenantonly birch phrase"], name="BM25 Cache B")
    monkeypatch.setattr(app_settings, "BM25_INDEX_CACHE_ENABLED", True)

    results_a = await rp.bm25_search(db_session, org_a, "tenantonly willow", top_k=5)
    results_b = await rp.bm25_search(db_session, org_b, "tenantonly birch", top_k=5)
    cached_a = await rp.bm25_search(db_session, org_a, "tenantonly willow", top_k=5)

    assert [row["chunk_id"] for row in results_a] == ids_a
    assert [row["chunk_id"] for row in results_b] == ids_b
    assert cached_a == results_a


async def test_a_chunk_found_by_both_hybrid_legs_keeps_the_semantic_legs_embedding(db_session):
    org_id, ids = await _org_with_chunks(db_session, ["quantum chromodynamics lecture notes", "grocery list eggs milk bread"])
    target = (await rp.fetch_organization_chunks(db_session, org_id))
    query_embedding = next(c["embedding"] for c in target if c["chunk_id"] == ids[0])  # nearest neighbour of chunk 0 is chunk 0

    results = await rp.hybrid_search(db_session, org_id, "quantum chromodynamics", top_k=2, query_embedding=query_embedding)

    both = next(r for r in results if r["chunk_id"] == ids[0])
    assert isinstance(both["embedding"], list) and len(both["embedding"]) == DIM


async def test_bm25_ranking_runs_off_the_event_loop(db_session, monkeypatch):
    """A deliberately slow, BLOCKING index build must not stall the event loop:
    a concurrent ticker has to keep ticking while `bm25_search` is running. (Run
    inline, the ticker would only advance after the whole blocking call.)"""
    org_id, _ = await _org_with_chunks(db_session, ["alpha beta gamma", "delta epsilon zeta"])

    class SlowBM25:
        def __init__(self, corpus):
            time.sleep(0.4)  # blocking on purpose
            self._n = len(corpus)

        def get_scores(self, query):
            return [1.0] * self._n

    monkeypatch.setattr(rp, "BM25Okapi", SlowBM25)
    ticks = 0

    async def ticker():
        nonlocal ticks
        while True:
            await asyncio.sleep(0.02)
            ticks += 1

    task = asyncio.create_task(ticker())
    await rp.bm25_search(db_session, org_id, "alpha", top_k=2)
    task.cancel()

    assert ticks >= 5, f"the event loop was blocked during the BM25 build (only {ticks} ticks in ~0.4 s)"


async def test_numpy_vector_ranking_still_returns_the_exact_nearest_neighbour(db_session):
    org_id, ids = await _org_with_chunks(db_session, ["one", "two", "three", "four"])
    chunks = await rp.fetch_organization_chunks(db_session, org_id)
    target = next(c for c in chunks if c["chunk_id"] == ids[2])

    results = await rp.rank_chunks_by_embedding(db_session, org_id, target["embedding"], top_k=2)

    assert results[0]["chunk_id"] == ids[2] and results[0]["score"] > 0.999
    assert len(results) == 2 and results[0]["score"] >= results[1]["score"]

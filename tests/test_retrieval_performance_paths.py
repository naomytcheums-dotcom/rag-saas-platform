"""Hardening Mission, §7 -- behaviours behind the measured retrieval speed-ups
(scripts/retrieval_benchmark.py, A/B on 5,000 chunks): the keyword leg no longer
loads every chunk's embedding (2.04 s -> 0.19 s), and the CPU-bound ranking runs
off the event loop. Real DB session, real rows, deterministic random embeddings
(no embedding model needed)."""

import asyncio
import time
import uuid

import numpy as np

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

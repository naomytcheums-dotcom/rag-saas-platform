import datetime as dt
import uuid

import pytest
from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.database import Base
from api.models.document import Document, DocumentChunk
from api.models.media import MediaAsset, MediaType
from api.models.organization import Organization
from api.services import retrieval_pipeline as rp


@pytest.fixture(autouse=True)
def clean_cache(monkeypatch):
    monkeypatch.setattr(settings, "BM25_INDEX_CACHE_ENABLED", True)
    monkeypatch.setattr(rp, "_BM25_INDEX_CACHE", rp.OrderedDict())


async def seed(db, org_id=None):
    org = Organization(id=org_id or uuid.uuid4(), name="Cache test", slug=uuid.uuid4().hex)
    doc = Document(
        id=uuid.uuid4(), organization_id=org.id, name="test.pdf", file_key="test",
        file_size=1, file_type="application/pdf",
    )
    db.add_all([org, doc])
    await db.flush()
    chunks = [
        DocumentChunk(
            id=uuid.uuid4(), organization_id=org.id, document_id=doc.id,
            content=text, embedding=[1.0], metadata_json={"group": group},
        )
        for text, group in (("cedar cedar forest", "a"), ("birch meadow", "b"), ("willow river", "a"))
    ]
    db.add_all(chunks)
    await db.commit()
    return org, doc, chunks


@pytest.mark.parametrize("filters", [
    {}, {"metadata_filters": {"group": "a"}},
    {"metadata_filters": {"group": {"in": ["a", "b"]}}},
    {"metadata_filters": {"group": "missing"}},
    {"document_ids": "selected"},
    {"metadata_filters": {"group": "b"}, "document_ids": "selected"},
])
async def test_cached_scores_and_order_equal_uncached(db_session, monkeypatch, filters):
    org, doc, _ = await seed(db_session)
    kwargs = dict(filters)
    if "document_ids" in kwargs:
        kwargs["document_ids"] = [doc.id]
    original = rp.fetch_organization_chunks
    calls = 0

    async def counted(*args, **kw):
        nonlocal calls
        calls += 1
        return await original(*args, **kw)

    monkeypatch.setattr(rp, "fetch_organization_chunks", counted)
    first = await rp.bm25_search(db_session, org.id, "cedar forest", top_k=3, **kwargs)
    assert await rp.bm25_search(db_session, org.id, "cedar forest", top_k=3, **kwargs) == first
    assert calls == 1
    monkeypatch.setattr(settings, "BM25_INDEX_CACHE_ENABLED", False)
    assert await rp.bm25_search(db_session, org.id, "cedar forest", top_k=3, **kwargs) == first
    assert calls == 2


async def test_revision_catches_external_bulk_reindex_and_delete(db_session, monkeypatch):
    org, doc, chunks = await seed(db_session)
    old = await rp.bm25_search(db_session, org.id, "cedar", top_k=3)
    revision = await db_session.scalar(select(Organization.bm25_corpus_revision).where(Organization.id == org.id))
    await db_session.commit()
    # A different process cannot notify this process's memory cache.
    monkeypatch.setattr(rp, "_evict_bm25_organization", lambda org: None)
    engine = db_session.bind
    async with engine.begin() as conn:
        await conn.execute(delete(DocumentChunk).where(DocumentChunk.organization_id == org.id))
        replacement = uuid.uuid4()
        await conn.execute(insert(DocumentChunk).values(
            id=replacement, organization_id=org.id, document_id=doc.id,
            content="new cedar text", embedding=[1.0],
        ))
    results = await rp.bm25_search(db_session, org.id, "cedar", top_k=3)
    assert {r["chunk_id"] for r in old} == {str(c.id) for c in chunks}
    assert [r["chunk_id"] for r in results] == [str(replacement)]
    assert await db_session.scalar(
        select(Organization.bm25_corpus_revision).where(Organization.id == org.id)
    ) > revision
    await db_session.commit()
    async with engine.begin() as conn:
        await conn.execute(delete(DocumentChunk).where(DocumentChunk.id == replacement))
    assert await rp.bm25_search(db_session, org.id, "cedar") == []


async def test_content_metadata_embedding_and_parent_changes_invalidate(db_session):
    org, doc, chunks = await seed(db_session)
    org_id, doc_id, chunk_id = org.id, doc.id, chunks[0].id
    kwargs = {"metadata_filters": {"group": "a"}}
    assert len(await rp.bm25_search(db_session, org_id, "cedar", **kwargs)) == 2
    await db_session.execute(update(DocumentChunk).where(DocumentChunk.id == chunk_id).values(
        metadata_json={"group": "b"}, content="updated cedar",
    ))
    await db_session.commit()
    results = await rp.bm25_search(db_session, org_id, "cedar", **kwargs)
    assert [r["chunk_id"] for r in results] == [str(chunks[2].id)]
    await db_session.execute(update(Document).where(Document.id == doc_id).values(name="renamed.pdf"))
    await db_session.commit()
    assert all(r["document_name"] == "renamed.pdf" for r in await rp.bm25_search(db_session, org_id, "cedar"))
    await db_session.execute(update(DocumentChunk).where(DocumentChunk.id == chunk_id).values(embedding=None))
    await db_session.commit()
    assert str(chunk_id) not in {r["chunk_id"] for r in await rp.bm25_search(db_session, org_id, "cedar")}
    await db_session.execute(update(Document).where(Document.id == doc_id).values(deleted_at=dt.datetime.now(dt.timezone.utc)))
    await db_session.commit()
    assert await rp.bm25_search(db_session, org_id, "cedar") == []
    await db_session.execute(update(Document).where(Document.id == doc_id).values(deleted_at=None))
    await db_session.commit()
    assert len(await rp.bm25_search(db_session, org_id, "cedar")) == 2


async def test_rollback_does_not_publish_uncommitted_index(db_session):
    org, _, chunks = await seed(db_session)
    org_id, chunk_id = org.id, chunks[0].id
    baseline = await rp.bm25_search(db_session, org_id, "cedar")
    await db_session.commit()
    await db_session.execute(update(DocumentChunk).where(DocumentChunk.id == chunk_id).values(content="uncommitted cedar"))
    changed = await rp.bm25_search(db_session, org_id, "cedar")
    assert any(r["content"] == "uncommitted cedar" for r in changed)
    assert all(c["content"] != "uncommitted cedar" for entry in rp._BM25_INDEX_CACHE.values() for c in entry[0])
    await db_session.rollback()
    assert await rp.bm25_search(db_session, org_id, "cedar") == baseline


async def test_media_chunk_delete_and_citation_update(db_session):
    org, _, _ = await seed(db_session)
    asset = MediaAsset(
        id=uuid.uuid4(), organization_id=org.id, media_type=MediaType.audio,
        filename="sound.wav", file_key="sound", file_size=1, mime_type="audio/wav",
    )
    chunk = DocumentChunk(
        organization_id=org.id, media_asset_id=asset.id, content="cedar sound", embedding=[1.0],
    )
    db_session.add_all([asset, chunk])
    await db_session.commit()
    org_id, asset_id, chunk_id = org.id, asset.id, chunk.id
    assert any(r["chunk_id"] == str(chunk_id) for r in await rp.bm25_search(db_session, org_id, "cedar"))
    await db_session.execute(update(MediaAsset).where(MediaAsset.id == asset_id).values(filename="renamed.wav"))
    await db_session.commit()
    result = next(r for r in await rp.bm25_search(db_session, org_id, "cedar") if r["chunk_id"] == str(chunk_id))
    assert result["document_name"] == "renamed.wav"
    await db_session.execute(delete(DocumentChunk).where(DocumentChunk.media_asset_id == asset_id))
    await db_session.delete(asset)
    await db_session.commit()
    assert str(chunk_id) not in {r["chunk_id"] for r in await rp.bm25_search(db_session, org_id, "cedar")}


async def test_lru_is_bounded_and_hits_refresh_recency(db_session, monkeypatch):
    org, _, _ = await seed(db_session)
    monkeypatch.setattr(rp, "_BM25_INDEX_CACHE_MAX_ENTRIES", 2)
    for group in ("a", "b", "a", "missing"):
        await rp.bm25_search(db_session, org.id, "cedar", metadata_filters={"group": group})
    keys = list(rp._BM25_INDEX_CACHE)
    assert len(keys) == 2
    assert [key[3] for key in keys] == ['{"group":"a"}', '{"group":"missing"}']


async def test_cached_metadata_is_not_mutable_by_callers(db_session):
    org, _, _ = await seed(db_session)
    first = await rp.bm25_search(db_session, org.id, "cedar")
    first[0]["metadata_json"]["group"] = "mutated"
    second = await rp.bm25_search(db_session, org.id, "cedar")
    assert second[0]["metadata_json"]["group"] == "a"


async def test_same_tenant_uuid_in_different_databases_never_shares_index(db_session):
    org, _, chunks = await seed(db_session)
    first = await rp.bm25_search(db_session, org.id, "cedar")
    other_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with other_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(other_engine, expire_on_commit=False)() as other:
            _, _, other_chunks = await seed(other, org.id)
            second = await rp.bm25_search(other, org.id, "cedar")
            assert {r["chunk_id"] for r in first} == {str(c.id) for c in chunks}
            assert {r["chunk_id"] for r in second} == {str(c.id) for c in other_chunks}
            assert not {r["chunk_id"] for r in first} & {r["chunk_id"] for r in second}
    finally:
        await other_engine.dispose()


async def test_commit_during_index_build_does_not_publish_old_revision(db_session, monkeypatch):
    org, doc, _ = await seed(db_session)
    org_id, doc_id = org.id, doc.id
    original = rp.fetch_organization_chunks

    async def fetch_then_commit(*args, **kwargs):
        rows = await original(*args, **kwargs)
        # Simulate another worker committing while this worker builds the index.
        await db_session.commit()
        async with db_session.bind.begin() as conn:
            await conn.execute(insert(DocumentChunk).values(
                organization_id=org_id, document_id=doc_id,
                content="concurrent cedar", embedding=[1.0],
            ))
        return rows

    monkeypatch.setattr(rp, "fetch_organization_chunks", fetch_then_commit)
    assert len(await rp.bm25_search(db_session, org_id, "cedar")) == 3
    assert not rp._BM25_INDEX_CACHE
    monkeypatch.setattr(rp, "fetch_organization_chunks", original)
    assert len(await rp.bm25_search(db_session, org_id, "cedar")) == 4


async def test_savepoint_commit_does_not_publish_outer_uncommitted_write(db_session):
    org, _, chunks = await seed(db_session)
    org_id, chunk_id = org.id, chunks[0].id
    async with db_session.begin_nested():
        await db_session.execute(
            update(DocumentChunk).where(DocumentChunk.id == chunk_id).values(content="savepoint cedar")
        )
    results = await rp.bm25_search(db_session, org_id, "cedar")
    assert any(r["content"] == "savepoint cedar" for r in results)
    assert not rp._BM25_INDEX_CACHE
    await db_session.rollback()


async def test_other_tenant_cache_survives_invalidation(db_session, monkeypatch):
    org_a, _, chunks_a = await seed(db_session)
    org_b, _, chunks_b = await seed(db_session)
    org_a_id, org_b_id, chunk_a_id = org_a.id, org_b.id, chunks_a[0].id
    await rp.bm25_search(db_session, org_a_id, "cedar")
    expected_b = await rp.bm25_search(db_session, org_b_id, "cedar")
    await db_session.execute(delete(DocumentChunk).where(DocumentChunk.id == chunk_a_id))
    await db_session.commit()

    async def must_not_fetch(*args, **kwargs):
        pytest.fail("another tenant's index was evicted")

    monkeypatch.setattr(rp, "fetch_organization_chunks", must_not_fetch)
    assert await rp.bm25_search(db_session, org_b_id, "cedar") == expected_b
    assert {r["chunk_id"] for r in expected_b} == {str(c.id) for c in chunks_b}


async def test_metadata_kill_switch_has_distinct_cache_key(db_session, monkeypatch):
    org, _, _ = await seed(db_session)
    kwargs = {"metadata_filters": {"group": "a"}}
    monkeypatch.setattr(settings, "METADATA_FILTERING_ENABLED", True)
    assert len(await rp.bm25_search(db_session, org.id, "cedar", **kwargs)) == 2
    monkeypatch.setattr(settings, "METADATA_FILTERING_ENABLED", False)
    assert len(await rp.bm25_search(db_session, org.id, "cedar", **kwargs)) == 3
    monkeypatch.setattr(settings, "METADATA_FILTERING_ENABLED", True)
    assert len(await rp.bm25_search(db_session, org.id, "cedar", **kwargs)) == 2

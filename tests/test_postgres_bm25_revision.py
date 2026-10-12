"""Migration 0144: the BM25 corpus revision moves once per transaction and organization, at COMMIT, and writers of one organization no longer wait for each other.

Real PostgreSQL (the disposable database of CI or of the local stack); skipped when it is unreachable or when 0144 is not applied.
Measured before 0144 (2026-10-12, statement-level triggers of 0133): a second transaction writing for the same organization waited 4 s for the first one.
"""

import asyncio
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from api.config import settings


@pytest.fixture
async def engine():
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            applied = await conn.scalar(text("SELECT count(*) FROM pg_proc WHERE proname = 'bm25_revision_bump'"))
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        pytest.skip(f"DATABASE_URL is not reachable ({exc})")
    if not applied:
        await engine.dispose()
        pytest.skip("migration 0144 is not applied on this database")
    yield engine
    await engine.dispose()


async def _organization_with_a_document(engine) -> tuple[uuid.UUID, uuid.UUID]:
    org, doc = uuid.uuid4(), uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(text("INSERT INTO organizations (id, name, slug) VALUES (:o, 'bm25', :s)"), {"o": org, "s": f"bm25-{org.hex[:12]}"})
        await conn.execute(
            text("INSERT INTO documents (id, organization_id, name, file_key, file_size, file_type, status) VALUES (:d, :o, 'a.txt', 'k/a', 1, 'text/plain', 'completed')"),
            {"d": doc, "o": org},
        )
    return org, doc


async def _revision(conn, org) -> int:
    return await conn.scalar(text("SELECT bm25_corpus_revision FROM organizations WHERE id = :o"), {"o": org})


async def _chunk(conn, org, doc, content="c") -> None:
    await conn.execute(
        text("INSERT INTO document_chunks (id, content, organization_id, document_id) VALUES (gen_random_uuid(), :c, :o, :d)"), {"c": content, "o": org, "d": doc}
    )


async def _cleanup(engine, *orgs) -> None:
    async with engine.begin() as conn:
        for org in orgs:
            await conn.execute(text("DELETE FROM document_chunks WHERE organization_id = :o"), {"o": org})
            await conn.execute(text("DELETE FROM documents WHERE organization_id = :o"), {"o": org})
            await conn.execute(text("DELETE FROM organizations WHERE id = :o"), {"o": org})


async def test_a_transaction_moves_the_revision_once_at_commit_whatever_the_number_of_statements(engine):
    org, doc = await _organization_with_a_document(engine)
    try:
        async with engine.connect() as conn:
            before = await _revision(conn, org)
        async with engine.begin() as conn:
            for i in range(5):
                await _chunk(conn, org, doc, f"chunk {i}")
            await conn.execute(text("UPDATE documents SET status = 'completed' WHERE id = :d"), {"d": doc})
        async with engine.connect() as conn:
            assert await _revision(conn, org) == before + 1
    finally:
        await _cleanup(engine, org)


async def test_writers_of_the_same_organization_do_not_wait_for_each_other(engine):
    org, doc = await _organization_with_a_document(engine)
    try:
        async with engine.connect() as first:
            before = await _revision(first, org)  # opens the first transaction (autobegin); it stays open below
            await _chunk(first, org, doc, "first, still open")
            # A second transaction writes for the same organization while the first one is open: it must finish (before 0144 it waited for the first to commit).
            async with engine.begin() as second:
                await asyncio.wait_for(_chunk(second, org, doc, "second"), timeout=2)
            async with engine.connect() as reader:
                assert await _revision(reader, org) == before + 1  # only the committed transaction is visible
            await first.commit()
        async with engine.connect() as conn:
            assert await _revision(conn, org) == before + 2  # one per transaction
    finally:
        await _cleanup(engine, org)


async def test_the_revision_is_not_visible_before_commit_and_a_rollback_leaves_it_unchanged(engine):
    org, doc = await _organization_with_a_document(engine)
    try:
        async with engine.connect() as conn:
            before = await _revision(conn, org)
        async with engine.connect() as writer:
            await writer.begin()
            await _chunk(writer, org, doc)
            async with engine.connect() as reader:
                assert await _revision(reader, org) == before
            await writer.rollback()
        async with engine.connect() as conn:
            assert await _revision(conn, org) == before
    finally:
        await _cleanup(engine, org)


async def test_another_organization_is_untouched_and_moving_a_chunk_bumps_both(engine):
    org_a, doc_a = await _organization_with_a_document(engine)
    org_b, _doc_b = await _organization_with_a_document(engine)
    try:
        async with engine.connect() as conn:
            before_a, before_b = await _revision(conn, org_a), await _revision(conn, org_b)
        async with engine.begin() as conn:
            await _chunk(conn, org_a, doc_a)
        async with engine.connect() as conn:
            assert (await _revision(conn, org_a), await _revision(conn, org_b)) == (before_a + 1, before_b)
        async with engine.begin() as conn:
            await conn.execute(text("UPDATE document_chunks SET organization_id = :b WHERE organization_id = :a"), {"a": org_a, "b": org_b})
        async with engine.connect() as conn:
            assert (await _revision(conn, org_a), await _revision(conn, org_b)) == (before_a + 2, before_b + 1)
    finally:
        await _cleanup(engine, org_a, org_b)

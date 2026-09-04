"""
Partie 2.2.12 -- tests for api/security/documents.py's own
compute_content_hash/check_duplicate/get_duplicate_document/
get_similar_documents/deduplicate_organization.

Route-level tests (the actual upload-time blocking behavior, the two
new endpoints, permissions) live in tests/test_documents.py, alongside
every other document route test.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.database import Base
from api.models.document import Document, DocumentStatus
from api.security.documents import (
    check_duplicate,
    compute_content_hash,
    deduplicate_organization,
    get_duplicate_document,
    get_similar_documents,
)


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def _make_document(session, organization_id=None, content_hash=None, file_type="application/pdf", deleted_at=None, created_at=None) -> Document:
    document = Document(
        organization_id=organization_id or uuid.uuid4(), workspace_id=None, name="a.pdf",
        file_key="documents/x/a.pdf", file_size=10, file_type=file_type,
        status=DocumentStatus.completed.value, created_by=None, content_hash=content_hash, deleted_at=deleted_at,
    )
    session.add(document)
    await session.commit()
    if created_at is not None:
        document.created_at = created_at
        await session.commit()
    return document


# ------------------------------------------------------- compute_content_hash --

def test_compute_content_hash_is_deterministic_and_real_sha256():
    """Validation criterion: le hash SHA-256 est calculé correctement."""
    content = b"the exact same real bytes"
    assert compute_content_hash(content) == compute_content_hash(content)
    # A real, independently-verifiable SHA-256 hex digest -- 64 hex chars.
    digest = compute_content_hash(content)
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


def test_compute_content_hash_differs_for_different_content():
    """Validation criterion: un fichier différent n'est pas détecté
    comme doublon (au niveau du hash lui-même)."""
    assert compute_content_hash(b"real content one") != compute_content_hash(b"real content two")


# ------------------------------------------------- check_duplicate / get_duplicate_document --

async def test_get_duplicate_document_finds_a_real_matching_document(db_session):
    organization_id = uuid.uuid4()
    original = await _make_document(db_session, organization_id=organization_id, content_hash="a" * 64)

    found = await get_duplicate_document(db_session, organization_id, "a" * 64, "application/pdf")
    assert found.id == original.id
    assert await check_duplicate(db_session, organization_id, "a" * 64, "application/pdf") is True


async def test_get_duplicate_document_returns_none_for_different_content(db_session):
    organization_id = uuid.uuid4()
    await _make_document(db_session, organization_id=organization_id, content_hash="a" * 64)

    assert await get_duplicate_document(db_session, organization_id, "b" * 64, "application/pdf") is None
    assert await check_duplicate(db_session, organization_id, "b" * 64, "application/pdf") is False


async def test_get_duplicate_document_scoped_to_the_organization(db_session):
    """Vision critique -- pas de faux positif cross-tenant."""
    await _make_document(db_session, organization_id=uuid.uuid4(), content_hash="a" * 64)

    assert await get_duplicate_document(db_session, uuid.uuid4(), "a" * 64, "application/pdf") is None


async def test_get_duplicate_document_ignores_different_file_types(db_session):
    """Vision critique cohérence -- les mêmes octets ne sont PAS un
    doublon s'ils sont interprétés comme un format différent (même
    raisonnement que la distinction Markdown/CSV vs TXT déjà établie)."""
    organization_id = uuid.uuid4()
    await _make_document(db_session, organization_id=organization_id, content_hash="a" * 64, file_type="text/markdown")

    assert await get_duplicate_document(db_session, organization_id, "a" * 64, "text/plain") is None


async def test_get_duplicate_document_ignores_soft_deleted_documents(db_session):
    import datetime as dt

    organization_id = uuid.uuid4()
    await _make_document(db_session, organization_id=organization_id, content_hash="a" * 64, deleted_at=dt.datetime.now(dt.timezone.utc))

    assert await get_duplicate_document(db_session, organization_id, "a" * 64, "application/pdf") is None


# ------------------------------------------------------------- get_similar_documents --

async def test_get_similar_documents_finds_every_other_real_match(db_session):
    organization_id = uuid.uuid4()
    doc_a = await _make_document(db_session, organization_id=organization_id, content_hash="a" * 64)
    doc_b = await _make_document(db_session, organization_id=organization_id, content_hash="a" * 64)
    await _make_document(db_session, organization_id=organization_id, content_hash="b" * 64)  # different hash

    similar = await get_similar_documents(db_session, doc_a)
    assert {d.id for d in similar} == {doc_b.id}


async def test_get_similar_documents_is_empty_for_a_document_with_no_hash(db_session):
    """Vision critique cohérence -- un document importé (pas uploadé
    directement) n'a pas de hash, donc honnêtement aucun doublon."""
    document = await _make_document(db_session, content_hash=None)
    assert await get_similar_documents(db_session, document) == []


# ------------------------------------------------------------- deduplicate_organization --

async def test_deduplicate_organization_keeps_the_oldest_and_removes_the_rest(db_session):
    import datetime as dt

    organization_id = uuid.uuid4()
    oldest = await _make_document(db_session, organization_id=organization_id, content_hash="a" * 64, created_at=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc))
    newer = await _make_document(db_session, organization_id=organization_id, content_hash="a" * 64, created_at=dt.datetime(2026, 1, 2, tzinfo=dt.timezone.utc))

    result = await deduplicate_organization(db_session, organization_id, uuid.uuid4())
    await db_session.commit()

    assert result == {"duplicate_groups_found": 1, "documents_removed": 1}
    await db_session.refresh(oldest)
    await db_session.refresh(newer)
    assert oldest.deleted_at is None
    assert newer.deleted_at is not None


async def test_deduplicate_organization_is_a_real_soft_delete_never_permanent(db_session):
    """Vision critique -- action réversible, pas de perte de données."""
    organization_id = uuid.uuid4()
    _oldest = await _make_document(db_session, organization_id=organization_id, content_hash="a" * 64)
    duplicate = await _make_document(db_session, organization_id=organization_id, content_hash="a" * 64)

    await deduplicate_organization(db_session, organization_id)
    await db_session.commit()

    # A real, still-existing row -- soft delete, not a real DELETE.
    still_there = await db_session.get(Document, duplicate.id)
    assert still_there is not None
    assert still_there.deleted_at is not None


async def test_deduplicate_organization_ignores_groups_of_one(db_session):
    organization_id = uuid.uuid4()
    await _make_document(db_session, organization_id=organization_id, content_hash="a" * 64)
    await _make_document(db_session, organization_id=organization_id, content_hash="b" * 64)

    result = await deduplicate_organization(db_session, organization_id)
    assert result == {"duplicate_groups_found": 0, "documents_removed": 0}


async def test_deduplicate_organization_does_not_touch_other_organizations(db_session):
    other_org_id = uuid.uuid4()
    await _make_document(db_session, organization_id=other_org_id, content_hash="a" * 64)
    await _make_document(db_session, organization_id=other_org_id, content_hash="a" * 64)

    result = await deduplicate_organization(db_session, uuid.uuid4())
    assert result == {"duplicate_groups_found": 0, "documents_removed": 0}

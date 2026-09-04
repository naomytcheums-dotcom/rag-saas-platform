"""
Partie 2.2.13 -- tests for api/security/documents.py's own
get_file_modified_time/check_document_modified/mark_document_checked/
get_outdated_documents.

Real network behavior of the underlying HTTP mechanism itself
(api/services/url_fetching.py's own get_url_last_modified) is tested
in tests/test_url_fetching.py (fast, mocked transport) and
tests/test_url_fetching_integration.py (real network) -- mocked here
at that same real call boundary, since these tests exist to prove
THIS module's own real orchestration (what gets compared, what gets
updated, how "outdated" is derived), not the HTTP mechanism a second
time.
"""

import datetime as dt
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.database import Base
from api.models.document import Document, DocumentStatus
from api.models.organization import Organization, OrganizationMember, OrganizationRole
from api.models.user import User
from api.security.documents import check_document_modified, get_file_modified_time, get_outdated_documents, mark_document_checked


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def _make_document(session, organization_id=None, source_url="https://example.com/report.pdf", last_modified=None, processed_at=None, deleted_at=None) -> Document:
    document = Document(
        organization_id=organization_id or uuid.uuid4(), workspace_id=None, name="a.pdf",
        file_key="documents/x/a.pdf", file_size=10, file_type="application/pdf",
        status=DocumentStatus.completed.value, created_by=None, source_url=source_url,
        last_modified=last_modified, processed_at=processed_at, deleted_at=deleted_at,
    )
    session.add(document)
    await session.commit()
    return document


# ------------------------------------------------------- get_file_modified_time --

async def test_get_file_modified_time_returns_none_without_a_source_url(db_session):
    """Vision critique cohérence -- un document uploadé directement n'a
    pas de source externe indépendante à vérifier."""
    document = await _make_document(db_session, source_url=None)
    assert await get_file_modified_time(document) is None


async def test_get_file_modified_time_delegates_to_the_real_url_check(db_session):
    document = await _make_document(db_session, source_url="https://example.com/report.pdf")
    fake_time = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)

    with patch("api.security.documents.get_url_last_modified", return_value=fake_time) as mock_check:
        result = await get_file_modified_time(document)

    assert result == fake_time
    mock_check.assert_called_once_with("https://example.com/report.pdf")


# ------------------------------------------------------- check_document_modified --

async def test_check_document_modified_detects_a_real_newer_modification(db_session):
    """Validation criterion: la détection de modification fonctionne."""
    old_time = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    new_time = dt.datetime(2026, 2, 1, tzinfo=dt.timezone.utc)
    document = await _make_document(db_session, last_modified=old_time)

    with patch("api.security.documents.get_url_last_modified", return_value=new_time):
        modified = await check_document_modified(document)

    assert modified is True
    assert document.last_modified == new_time


async def test_check_document_modified_is_false_when_unchanged(db_session):
    same_time = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    document = await _make_document(db_session, last_modified=same_time)

    with patch("api.security.documents.get_url_last_modified", return_value=same_time):
        modified = await check_document_modified(document)

    assert modified is False
    assert document.last_modified == same_time


async def test_check_document_modified_is_false_and_never_a_false_positive_when_source_is_unreachable(db_session):
    """Vision critique 3 -- que se passe-t-il si la source est
    inaccessible : jamais un faux positif."""
    document = await _make_document(db_session, last_modified=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc))

    with patch("api.security.documents.get_url_last_modified", return_value=None):
        modified = await check_document_modified(document)

    assert modified is False


async def test_check_document_modified_sets_last_modified_the_first_time(db_session):
    """A document never checked before (`last_modified IS NULL`) gets a
    real first value, correctly counted as a real, new modification."""
    document = await _make_document(db_session, last_modified=None)
    fresh_time = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)

    with patch("api.security.documents.get_url_last_modified", return_value=fresh_time):
        modified = await check_document_modified(document)

    assert modified is True
    assert document.last_modified == fresh_time


# ------------------------------------------------------------- mark_document_checked --

def test_mark_document_checked_stamps_a_real_current_timestamp():
    document = Document(
        organization_id=uuid.uuid4(), name="a.pdf", file_key="k", file_size=1, file_type="application/pdf",
        status=DocumentStatus.completed.value,
    )
    assert document.last_checked is None
    mark_document_checked(document)
    assert document.last_checked is not None
    assert document.last_checked.tzinfo is not None


# ------------------------------------------------------------- get_outdated_documents --

async def _make_membership(session, user_id, organization_id) -> None:
    session.add(OrganizationMember(organization_id=organization_id, user_id=user_id, role=OrganizationRole.member))
    await session.commit()


async def _make_user_and_org(session) -> tuple[uuid.UUID, uuid.UUID]:
    user = User(email=f"outdated-{uuid.uuid4().hex[:8]}@example.com", hashed_password="irrelevant")
    session.add(user)
    await session.flush()
    organization = Organization(name="Acme", slug=f"acme-{uuid.uuid4().hex[:8]}")
    session.add(organization)
    await session.flush()
    await session.commit()
    return user.id, organization.id


async def test_get_outdated_documents_finds_a_real_stale_document(db_session):
    """Validation criterion: les documents modifiés sont listés."""
    user_id, org_id = await _make_user_and_org(db_session)
    await _make_membership(db_session, user_id, org_id)
    processed = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    stale_source = dt.datetime(2026, 2, 1, tzinfo=dt.timezone.utc)
    outdated = await _make_document(db_session, organization_id=org_id, last_modified=stale_source, processed_at=processed)

    results = await get_outdated_documents(db_session, user_id)
    assert {d.id for d in results} == {outdated.id}


async def test_get_outdated_documents_excludes_a_document_that_is_still_current(db_session):
    user_id, org_id = await _make_user_and_org(db_session)
    await _make_membership(db_session, user_id, org_id)
    processed = dt.datetime(2026, 2, 1, tzinfo=dt.timezone.utc)
    source_time = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)  # older than processed_at
    await _make_document(db_session, organization_id=org_id, last_modified=source_time, processed_at=processed)

    assert await get_outdated_documents(db_session, user_id) == []


async def test_get_outdated_documents_excludes_a_document_never_checked(db_session):
    """Vision critique -- "jamais vérifié" n'est pas la même chose que
    "obsolète"."""
    user_id, org_id = await _make_user_and_org(db_session)
    await _make_membership(db_session, user_id, org_id)
    await _make_document(db_session, organization_id=org_id, last_modified=None, processed_at=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc))

    assert await get_outdated_documents(db_session, user_id) == []


async def test_get_outdated_documents_excludes_soft_deleted_documents(db_session):
    user_id, org_id = await _make_user_and_org(db_session)
    await _make_membership(db_session, user_id, org_id)
    await _make_document(
        db_session, organization_id=org_id,
        last_modified=dt.datetime(2026, 2, 1, tzinfo=dt.timezone.utc), processed_at=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
        deleted_at=dt.datetime.now(dt.timezone.utc),
    )

    assert await get_outdated_documents(db_session, user_id) == []


async def test_get_outdated_documents_only_covers_organizations_the_caller_is_a_member_of(db_session):
    """Vision critique -- pas de fuite cross-tenant."""
    user_id, _my_org_id = await _make_user_and_org(db_session)
    _other_user_id, other_org_id = await _make_user_and_org(db_session)
    await _make_document(
        db_session, organization_id=other_org_id,
        last_modified=dt.datetime(2026, 2, 1, tzinfo=dt.timezone.utc), processed_at=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
    )

    assert await get_outdated_documents(db_session, user_id) == []

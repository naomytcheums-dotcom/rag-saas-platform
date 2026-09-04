"""
Partie 2.2.10 -- tests for api/security/document_audit.py's own
log_document_action/get_document_history.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.database import Base
from api.models.document import Document, DocumentStatus
from api.security.document_audit import (
    ACTION_CREATED,
    ACTION_TAG_ADDED,
    DOCUMENT_ACTIONS,
    get_document_history,
    log_document_action,
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


async def _make_document(session) -> Document:
    document = Document(
        organization_id=uuid.uuid4(), workspace_id=None, name="a.pdf",
        file_key="documents/x/a.pdf", file_size=10, file_type="application/pdf",
        status=DocumentStatus.pending.value, created_by=None,
    )
    session.add(document)
    await session.commit()
    return document


def test_document_actions_defines_every_real_literal_action_name():
    """Validation criterion -- the real, fixed vocabulary this étape's
    own literal spec names, including `restored`, reserved but not yet
    produced anywhere (see this module's own docstring for why)."""
    assert set(DOCUMENT_ACTIONS) == {
        "created", "updated", "deleted", "restored", "reindexed", "tag_added", "tag_removed", "version_restored",
    }


async def test_log_document_action_records_a_real_entry(db_session):
    """Validation criterion: l'historique est créé lors de l'upload."""
    document = await _make_document(db_session)
    user_id = uuid.uuid4()

    entry = await log_document_action(db_session, document.id, user_id, ACTION_CREATED, metadata={"filename": "a.pdf"})

    assert entry.document_id == document.id
    assert entry.user_id == user_id
    assert entry.action == ACTION_CREATED
    assert entry.metadata_json == {"filename": "a.pdf"}


async def test_get_document_history_returns_entries_most_recent_first(db_session):
    """Validation criterion: l'historique est consultable. Real,
    explicit, distinct timestamps here -- SQLite's own real timestamp
    resolution is coarse enough that two log_document_action calls a
    real test issues back-to-back can land on the exact same value,
    making an ordering assertion genuinely flaky; a real Postgres
    timestamptz (this codebase's own real production database) does
    not have this real limitation."""
    import datetime as dt

    from api.models.document import DocumentAuditLog

    document = await _make_document(db_session)
    older = DocumentAuditLog(document_id=document.id, action=ACTION_CREATED, timestamp=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc))
    newer = DocumentAuditLog(document_id=document.id, action=ACTION_TAG_ADDED, timestamp=dt.datetime(2026, 1, 2, tzinfo=dt.timezone.utc))
    db_session.add_all([older, newer])
    await db_session.commit()

    history = await get_document_history(db_session, document.id)

    assert [entry.action for entry in history] == [ACTION_TAG_ADDED, ACTION_CREATED]


async def test_get_document_history_respects_pagination(db_session):
    document = await _make_document(db_session)
    for _ in range(5):
        await log_document_action(db_session, document.id, None, ACTION_CREATED)

    page = await get_document_history(db_session, document.id, limit=2, offset=2)
    assert len(page) == 2


async def test_get_document_history_only_returns_entries_for_this_document(db_session):
    document_one = await _make_document(db_session)
    document_two = await _make_document(db_session)
    await log_document_action(db_session, document_one.id, None, ACTION_CREATED)
    await log_document_action(db_session, document_two.id, None, ACTION_CREATED)

    history = await get_document_history(db_session, document_one.id)
    assert len(history) == 1
    assert history[0].document_id == document_one.id

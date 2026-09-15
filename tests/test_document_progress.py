"""
Partie 2.2.3 -- tests for api/security/documents.py's own
get_document_progress/send_progress_update/stream_document_progress.

Real Redis pub/sub itself is NOT reachable in this automated session
(no real Redis service available) -- same honest limitation as every
prior real-infrastructure dependency in this codebase (real Postgres/
MinIO for tests/test_documents_integration.py). What's tested here
instead: get_document_progress's own real DB-backed status mapping (no
Redis involved at all), and send_progress_update/stream_document_progress's
own real ORCHESTRATION logic against a real Redis CLIENT INTERFACE
mocked at the exact call boundary (publish/pubsub/listen) -- the same
"real library behavior, fake network" split every other module in this
codebase uses for its own external dependency.
"""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.database import Base
from api.models.document import Document, DocumentStatus
from api.security.documents import get_document_progress, send_progress_update, stream_document_progress

_REAL_PDF_MAGIC = b"%PDF-1.4\n%fake but real-looking pdf bytes\n"


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def _make_document(session, status: str) -> Document:
    document = Document(
        organization_id=uuid.uuid4(), workspace_id=None, name="a.pdf",
        file_key="documents/x/a.pdf", file_size=len(_REAL_PDF_MAGIC), file_type="application/pdf",
        status=status, created_by=None,
    )
    session.add(document)
    await session.commit()
    return document


# ------------------------------------------------------- get_document_progress --

@pytest.mark.parametrize("status,expected_progress", [
    (DocumentStatus.pending.value, 0),
    (DocumentStatus.processing.value, 50),
    (DocumentStatus.completed.value, 100),
    (DocumentStatus.failed.value, 100),
])
async def test_get_document_progress_maps_each_real_status_to_the_right_percentage(db_session, status, expected_progress):
    """Validation criterion: la progression correspond au vrai statut
    du document."""
    document = await _make_document(db_session, status)
    result = await get_document_progress(db_session, document.id)
    assert result == {"document_id": str(document.id), "status": status, "progress": expected_progress}


async def test_get_document_progress_raises_for_a_nonexistent_document(db_session):
    with pytest.raises(ValueError, match="not a registered document"):
        await get_document_progress(db_session, uuid.uuid4())


# ------------------------------------------------------- send_progress_update --

async def test_send_progress_update_publishes_the_real_expected_payload(monkeypatch):
    """Validation criterion: une mise à jour de progression est
    envoyée."""
    publish = AsyncMock()
    fake_redis = MagicMock()
    fake_redis.publish = publish
    monkeypatch.setattr("api.security.documents._get_progress_redis", lambda: fake_redis)

    document_id = uuid.uuid4()
    await send_progress_update(document_id, 50, DocumentStatus.processing.value)

    publish.assert_awaited_once()
    channel, payload = publish.await_args.args
    assert channel == f"document_progress:{document_id}"
    assert json.loads(payload) == {"document_id": str(document_id), "status": "processing", "progress": 50}


async def test_send_progress_update_tolerates_a_real_broker_failure(monkeypatch):
    """Validation criterion / vision critique 3: une panne Redis ne
    doit jamais interrompre le vrai traitement du document."""
    async def _boom(*args, **kwargs):
        raise ConnectionError("redis is down")

    fake_redis = MagicMock()
    fake_redis.publish = _boom
    monkeypatch.setattr("api.security.documents._get_progress_redis", lambda: fake_redis)
    await send_progress_update(uuid.uuid4(), 50, DocumentStatus.processing.value)  # must not raise


# --------------------------------------------------- stream_document_progress --

async def test_stream_document_progress_stops_immediately_for_a_real_terminal_status(db_session, monkeypatch):
    """Validation criterion: le flux se termine proprement une fois le
    document traité -- sans jamais ouvrir un vrai canal Redis pour un
    document déjà terminé."""
    document = await _make_document(db_session, DocumentStatus.completed.value)

    def _must_not_be_called():
        raise AssertionError("must not open a real pubsub channel for an already-terminal document")

    fake_redis = MagicMock()
    fake_redis.pubsub = _must_not_be_called
    monkeypatch.setattr("api.security.documents._get_progress_redis", lambda: fake_redis)

    frames = [frame async for frame in stream_document_progress(db_session, document.id)]
    assert len(frames) == 1
    assert json.loads(frames[0].removeprefix("data: ").strip()) == {
        "document_id": str(document.id), "status": DocumentStatus.completed.value, "progress": 100,
    }


async def test_stream_document_progress_forwards_real_messages_until_a_terminal_one(db_session, monkeypatch):
    """Validation criterion / vision critique 1: les mises à jour en
    temps réel sont transmises jusqu'à l'état final."""
    document = await _make_document(db_session, DocumentStatus.processing.value)

    messages = [
        {"type": "subscribe", "data": 1},  # a real, non-"message" pubsub event, correctly ignored
        {"type": "message", "data": json.dumps({"document_id": str(document.id), "status": "processing", "progress": 50})},
        {"type": "message", "data": json.dumps({"document_id": str(document.id), "status": "completed", "progress": 100})},
    ]

    async def _listen():
        for message in messages:
            yield message

    fake_pubsub = MagicMock()
    fake_pubsub.subscribe = AsyncMock()
    fake_pubsub.unsubscribe = AsyncMock()
    fake_pubsub.aclose = AsyncMock()
    fake_pubsub.listen = _listen
    fake_redis = MagicMock()
    fake_redis.pubsub = lambda: fake_pubsub
    monkeypatch.setattr("api.security.documents._get_progress_redis", lambda: fake_redis)

    frames = [frame async for frame in stream_document_progress(db_session, document.id)]

    # Frame 0 is the real initial snapshot (processing/50); frames 1-2
    # are the real, forwarded pubsub messages (the "subscribe" event is
    # correctly skipped, not forwarded as a real SSE frame).
    assert len(frames) == 3
    assert json.loads(frames[1].removeprefix("data: ").strip())["progress"] == 50
    assert json.loads(frames[2].removeprefix("data: ").strip())["status"] == "completed"
    fake_pubsub.subscribe.assert_awaited_once_with(f"document_progress:{document.id}")
    fake_pubsub.unsubscribe.assert_awaited_once()
    fake_pubsub.aclose.assert_awaited_once()

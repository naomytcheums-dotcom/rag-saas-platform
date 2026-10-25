"""api/tasks/media.py: the Celery sweeps over media assets.

Each sweep must pick exactly the assets it is meant for, skip the ones already done, survive one asset's failure, and report how many it
handled. The services they call (transcription, vision, frame extraction, storage) are replaced; the selection, the skipping, the writes
and the commit run for real on the test database. `_session_factory` is pointed at the test session, like
tests/test_p0_media_filename_path.py does.
"""

import datetime as dt
import logging
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from api.config import settings
from api.models.document import DocumentChunk
from api.models.media import MediaAsset, MediaFrame, MediaStatus, MediaTranscript, MediaType
from api.models.user import User
from api.tasks import media as media_tasks


@pytest.fixture
async def owner(client, db_session):
    email = f"media-tasks-{uuid.uuid4().hex[:8]}@example.com"
    token = (await client.post("/auth/register", json={"email": email, "password": "correct-horse-battery-staple", "accept_terms": True})).json()["access_token"]
    org = (await client.post("/organizations", json={"name": "Media tasks"}, headers={"Authorization": f"Bearer {token}"})).json()
    user = await db_session.scalar(select(User).where(User.email == email))
    return uuid.UUID(org["id"]), user.id


@pytest.fixture
def task_session(monkeypatch, db_session):
    disposed = []

    class _Engine:
        async def dispose(self):
            disposed.append(True)

    @asynccontextmanager
    async def _session():
        yield db_session

    monkeypatch.setattr(media_tasks, "_session_factory", lambda: (_Engine(), _session))
    return disposed


async def _asset(db_session, owner, media_type, status=MediaStatus.completed, **fields):
    org_id, user_id = owner
    asset = MediaAsset(
        organization_id=org_id, uploaded_by=user_id, media_type=media_type, status=status, filename=f"{media_type.value}-{uuid.uuid4().hex[:6]}",
        file_key=f"media/{uuid.uuid4().hex}", file_size=10, mime_type={"audio": "audio/mpeg", "video": "video/mp4", "image": "image/png"}[media_type.value],
        **fields,
    )
    db_session.add(asset)
    await db_session.commit()
    return asset


async def test_transcripts_sweep_only_fills_completed_audio_without_a_transcript(db_session, owner, task_session, monkeypatch, caplog):
    todo = await _asset(db_session, owner, MediaType.audio)
    broken = await _asset(db_session, owner, MediaType.audio)
    done = await _asset(db_session, owner, MediaType.audio)
    db_session.add(MediaTranscript(media_asset_id=done.id, text="already there"))
    await _asset(db_session, owner, MediaType.audio, status=MediaStatus.processing)
    await _asset(db_session, owner, MediaType.video)
    await db_session.commit()
    seen = []

    async def fake_transcribe(db, asset):
        seen.append(asset.id)
        if asset.id == broken.id:
            raise RuntimeError("whisper timed out")
        db.add(MediaTranscript(media_asset_id=asset.id, text="hello"))

    monkeypatch.setattr("api.services.media.extract_audio_transcript", fake_transcribe)

    with caplog.at_level(logging.WARNING, logger="api.tasks.media"):
        assert await media_tasks._extract_transcripts_async() == 1

    assert sorted(seen) == sorted([todo.id, broken.id])
    assert f"asset '{broken.id}' failed: whisper timed out" in caplog.text
    await db_session.rollback()  # the sweep committed its work
    transcripts = (await db_session.scalars(select(MediaTranscript.media_asset_id))).all()
    assert sorted(transcripts) == sorted([todo.id, done.id])
    assert task_session == [True]


async def test_frames_sweep_skips_videos_that_have_frames_and_survives_a_download_failure(db_session, owner, task_session, monkeypatch, caplog):
    todo = await _asset(db_session, owner, MediaType.video)
    missing_file = await _asset(db_session, owner, MediaType.video)
    has_frames = await _asset(db_session, owner, MediaType.video)
    db_session.add(MediaFrame(media_asset_id=has_frames.id, frame_index=0, timestamp_ms=0, file_key="frames/0"))
    await db_session.commit()

    def fake_download(key):
        if key == missing_file.file_key:
            raise FileNotFoundError(key)
        return b"mp4-bytes"

    extracted = []

    async def fake_extract(db, asset, video_path):
        with open(video_path, "rb") as handle:
            extracted.append((asset.id, handle.read()))

    monkeypatch.setattr("api.services.document_storage.download_document_file", fake_download)
    monkeypatch.setattr("api.services.media.extract_video_frames", fake_extract)

    with caplog.at_level(logging.WARNING, logger="api.tasks.media"):
        assert await media_tasks._extract_frames_async() == 1

    assert extracted == [(todo.id, b"mp4-bytes")]
    assert f"extract_frames: asset '{missing_file.id}' failed" in caplog.text


async def test_describe_sweep_stores_the_vision_result_and_indexes_the_image(db_session, owner, task_session, monkeypatch, caplog):
    plain = await _asset(db_session, owner, MediaType.image)
    no_objects = await _asset(db_session, owner, MediaType.image)
    failing = await _asset(db_session, owner, MediaType.image)
    described = await _asset(db_session, owner, MediaType.image, description="kept as is")
    results = {
        plain.file_key: {"description": "a red bicycle", "objects": ["bicycle"], "tags": ["outdoor"]},
        no_objects.file_key: {"description": "a blank wall", "objects": [], "tags": []},
    }
    monkeypatch.setattr("api.services.document_storage.download_document_file", lambda key: key.encode())

    async def fake_describe(content, mime_type):
        assert mime_type == "image/png"
        if content.decode() == failing.file_key:
            raise RuntimeError("vision provider down")
        return results[content.decode()]

    index = AsyncMock()
    monkeypatch.setattr("api.services.media.describe_image", fake_describe)
    monkeypatch.setattr("api.services.media.index_media_in_rag", index)

    with caplog.at_level(logging.WARNING, logger="api.tasks.media"):
        assert await media_tasks._describe_media_async() == 2

    await db_session.rollback()
    for asset in (plain, no_objects, failing, described):
        await db_session.refresh(asset)
    assert (plain.description, plain.objects_json, plain.tags_json) == ("a red bicycle", ["bicycle"], ["outdoor"])
    assert (no_objects.description, no_objects.objects_json, no_objects.tags_json) == ("a blank wall", None, None)  # empty lists stored as NULL
    assert failing.description is None and described.description == "kept as is"
    assert sorted(call.args[1].id for call in index.await_args_list) == sorted([plain.id, no_objects.id])
    assert f"describe_media: asset '{failing.id}' failed: vision provider down" in caplog.text


async def test_index_sweep_only_indexes_completed_assets_without_chunks(db_session, owner, task_session, monkeypatch, caplog):
    org_id, _ = owner
    todo = await _asset(db_session, owner, MediaType.image)
    failing = await _asset(db_session, owner, MediaType.audio)
    indexed = await _asset(db_session, owner, MediaType.image)
    db_session.add(DocumentChunk(organization_id=org_id, media_asset_id=indexed.id, content="already indexed"))
    await _asset(db_session, owner, MediaType.image, status=MediaStatus.failed)
    await db_session.commit()
    calls = []

    async def fake_index(db, asset):
        calls.append(asset.id)
        if asset.id == failing.id:
            raise RuntimeError("embedding quota")

    monkeypatch.setattr("api.services.media.index_media_in_rag", fake_index)

    with caplog.at_level(logging.WARNING, logger="api.tasks.media"):
        assert await media_tasks._index_media_in_rag_async() == 1

    assert sorted(calls) == sorted([todo.id, failing.id])
    assert f"asset '{failing.id}' failed: embedding quota" in caplog.text


async def test_cleanup_deletes_only_old_failed_assets_and_their_stored_files(db_session, owner, task_session, monkeypatch, caplog):
    long_ago = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=40)
    old_failed = await _asset(db_session, owner, MediaType.video, status=MediaStatus.failed, created_at=long_ago)
    db_session.add(MediaFrame(media_asset_id=old_failed.id, frame_index=0, timestamp_ms=0, file_key="frames/old-0"))
    undeletable = await _asset(db_session, owner, MediaType.image, status=MediaStatus.failed, created_at=long_ago)
    recent_failed = await _asset(db_session, owner, MediaType.image, status=MediaStatus.failed)
    old_completed = await _asset(db_session, owner, MediaType.image, created_at=long_ago)
    await db_session.commit()
    deleted_keys = []

    def fake_delete(key):
        if key == undeletable.file_key:
            raise RuntimeError("S3 refused")
        deleted_keys.append(key)

    monkeypatch.setattr("api.services.media.delete_document_file", fake_delete)

    with caplog.at_level(logging.WARNING, logger="api.tasks.media"):
        assert await media_tasks._cleanup_old_media_async(30) == 1

    assert sorted(deleted_keys) == sorted(["frames/old-0", old_failed.file_key])
    assert f"cleanup_old_media: asset '{undeletable.id}' failed: S3 refused" in caplog.text
    await db_session.rollback()
    remaining = set((await db_session.scalars(select(MediaAsset.id))).all())
    assert old_failed.id not in remaining
    assert {undeletable.id, recent_failed.id, old_completed.id} <= remaining


async def test_processing_task_reports_the_final_status_or_not_found(db_session, owner, task_session, monkeypatch):
    asset = await _asset(db_session, owner, MediaType.image, status=MediaStatus.pending)

    async def fake_process(db, media_asset_id):
        processed = await db.get(MediaAsset, media_asset_id)
        if processed is None:
            from api.services.media import MediaNotFoundError

            raise MediaNotFoundError(str(media_asset_id))
        processed.status = MediaStatus.completed
        return processed

    monkeypatch.setattr("api.services.media.process_media_asset", fake_process)

    assert await media_tasks._process_media_asset_async(str(asset.id)) == "completed"
    await db_session.rollback()
    await db_session.refresh(asset)
    assert asset.status == MediaStatus.completed  # committed by the task
    assert await media_tasks._process_media_asset_async(str(uuid.uuid4())) == "not_found"


def test_the_celery_entry_points_run_their_sweep_with_the_configured_values(monkeypatch):
    received = {}

    def recorder(name, value):
        async def _fake(*args):
            received[name] = args
            return value

        return _fake

    monkeypatch.setattr(media_tasks, "_process_media_asset_async", recorder("process", "completed"))
    monkeypatch.setattr(media_tasks, "_extract_transcripts_async", recorder("transcripts", 3))
    monkeypatch.setattr(media_tasks, "_extract_frames_async", recorder("frames", 4))
    monkeypatch.setattr(media_tasks, "_describe_media_async", recorder("describe", 5))
    monkeypatch.setattr(media_tasks, "_index_media_in_rag_async", recorder("index", 6))
    monkeypatch.setattr(media_tasks, "_cleanup_old_media_async", recorder("cleanup", 7))
    monkeypatch.setattr(settings, "MEDIA_CLEANUP_FAILED_AFTER_DAYS", 12)

    assert media_tasks.process_media_asset_task.run("abc") == "completed"
    assert (media_tasks.extract_transcripts.run(), media_tasks.extract_frames.run(), media_tasks.describe_media.run()) == (3, 4, 5)
    assert media_tasks.index_media_in_rag_task.run() == 6
    assert media_tasks.cleanup_old_media.run() == 7
    assert received["process"] == ("abc",) and received["cleanup"] == (12,)


def test_scheduling_dispatches_the_id_as_text_and_never_raises(monkeypatch, caplog):
    sent = []
    monkeypatch.setattr(media_tasks.process_media_asset_task, "delay", lambda media_id: sent.append(media_id))
    asset_id = uuid.uuid4()
    media_tasks.schedule_media_processing(asset_id)
    assert sent == [str(asset_id)]

    def broker_down(media_id):
        raise ConnectionError("redis unreachable")

    monkeypatch.setattr(media_tasks.process_media_asset_task, "delay", broker_down)
    with caplog.at_level(logging.WARNING, logger="api.tasks.media"):
        media_tasks.schedule_media_processing(asset_id)
    assert f"could not schedule processing for media asset '{asset_id}': redis unreachable" in caplog.text

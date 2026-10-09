"""SEC-003: the client-supplied name of an uploaded media file must never become a filesystem path.

Before the fix `Path(tmp_dir) / asset.filename` let `/abs/path` or `../..` escape the temporary directory, so a video upload
could overwrite any file the worker may write. These tests cover the sanitizer, the upload route, both processing paths that write a
temporary file, and the Content-Disposition header. Storage, ffmpeg and the LLM are stubbed; nothing leaves the test database."""

import io
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import select

from api.models.media import MediaAsset, MediaStatus, MediaType
from api.services.media import media_temp_filename, process_media_asset, sanitize_media_filename
from api.models.user import User


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("raw, expected", [
    ("photo.png", "photo.png"),
    ("my holiday video.mp4", "my holiday video.mp4"),
    ("/app/api/x.py", "x.py"),
    ("../../app/api/x.py", "x.py"),
    ("..\\..\\windows\\x.mp4", "x.mp4"),
    ("a/b\\c.mp4", "c.mp4"),
    ("..", "media"),
    (".", "media"),
    ("", "media"),
    (None, "media"),
    ("   ", "media"),
    ("...hidden.mp4", "hidden.mp4"),
    ('x";y.mp4', "x__y.mp4"),
    ("nul\x00byte.mp4", "nul_byte.mp4"),
    ("new\nline.mp4", "new_line.mp4"),
    ("vidéo été.mp4", "vidéo été.mp4"),
])
def test_sanitize_media_filename(raw, expected):
    assert sanitize_media_filename(raw) == expected


def test_sanitize_media_filename_caps_length_and_keeps_extension():
    cleaned = sanitize_media_filename("a" * 600 + ".mp4")
    assert len(cleaned) == 255
    assert cleaned.endswith(".mp4")
    assert len(sanitize_media_filename("b" * 600)) == 255


@pytest.mark.parametrize("filename, mime, expected_suffix", [
    ("clip.MP4", "video/mp4", ".mp4"),
    ("clip.mov", "video/quicktime", ".mov"),
    ("clip.py", "video/mp4", ".mp4"),
    ("/app/api/x.py", "video/webm", ".webm"),
    ("clip.sh", "video/unknown", ".bin"),
    ("noextension", "video/x-matroska", ".mkv"),
])
def test_media_temp_filename_is_generated_with_an_allow_listed_extension(filename, mime, expected_suffix):
    asset = MediaAsset(id=uuid.uuid4(), filename=filename, mime_type=mime)
    name = media_temp_filename(asset)
    assert name == f"{asset.id}{expected_suffix}"
    assert Path(name).name == name


async def _owner_and_org(client, register_payload):
    token = (await client.post("/auth/register", json={**register_payload, "accept_terms": True})).json()["access_token"]
    org_id = (await client.post("/organizations", json={"name": "Sec003"}, headers=_auth(token))).json()["id"]
    return token, org_id


@pytest.mark.parametrize("hostile", ["/app/api/x.py", "../../app/api/x.py", "..\\..\\x.mp4", "///etc/cron.d/job"])
async def test_upload_stores_only_a_sanitized_name(client, register_payload, monkeypatch, hostile):
    stored = {}

    def fake_upload(org_id, asset_id, filename, content, mime_type):
        stored["filename"] = filename
        return f"media/{org_id}/{asset_id}/{filename}"

    monkeypatch.setattr("api.services.media.upload_media_file", fake_upload)
    monkeypatch.setattr("api.routers.media.schedule_media_processing", Mock())
    token, org_id = await _owner_and_org(client, register_payload)

    response = await client.post(
        f"/organizations/{org_id}/media", files={"file": (hostile, io.BytesIO(b"x" * 16), "video/mp4")}, headers=_auth(token),
    )

    assert response.status_code == 201, response.text
    name = response.json()["filename"]
    assert name == stored["filename"]
    assert "/" not in name and "\\" not in name and ".." not in name


async def test_upload_without_a_usable_name_falls_back_to_a_default(client, register_payload, monkeypatch):
    monkeypatch.setattr("api.services.media.upload_media_file", lambda org_id, asset_id, filename, content, mime_type: f"media/{org_id}/{asset_id}/{filename}")
    monkeypatch.setattr("api.routers.media.schedule_media_processing", Mock())
    token, org_id = await _owner_and_org(client, register_payload)

    response = await client.post(
        f"/organizations/{org_id}/media", files={"file": ("..", io.BytesIO(b"x" * 16), "video/mp4")}, headers=_auth(token),
    )

    assert response.status_code == 201, response.text
    assert response.json()["filename"] == "media"


async def _hostile_video_asset(db_session, org_id, filename):
    user = await db_session.scalar(select(User))
    asset = MediaAsset(
        organization_id=uuid.UUID(org_id), uploaded_by=user.id, media_type=MediaType.video, status=MediaStatus.pending,
        filename=filename, file_key="media/seed", file_size=12, mime_type="video/mp4",
    )
    db_session.add(asset)
    await db_session.commit()
    return asset


async def test_process_video_never_writes_outside_its_temporary_directory(client, db_session, register_payload, monkeypatch, tmp_path):
    """Rows created before the fix may already hold a hostile name: processing must not trust the stored value either."""
    _token, org_id = await _owner_and_org(client, register_payload)
    canary = tmp_path / "must-not-be-written.mp4"
    asset = await _hostile_video_asset(db_session, org_id, str(canary))
    seen = {}

    def fake_duration(video_path):
        seen["path"] = Path(video_path)
        seen["content"] = Path(video_path).read_bytes()
        return 1000

    monkeypatch.setattr("api.services.media.download_document_file", lambda key: b"video-bytes")
    monkeypatch.setattr("api.services.media.get_video_duration_ms", fake_duration)
    monkeypatch.setattr("api.services.media.extract_video_transcript", AsyncMock())
    monkeypatch.setattr("api.services.media.extract_video_frames", AsyncMock())
    monkeypatch.setattr("api.services.media.describe_video", AsyncMock(return_value="summary"))
    monkeypatch.setattr("api.services.media.index_media_in_rag", AsyncMock())

    await process_media_asset(db_session, asset.id)

    assert not canary.exists()
    assert seen["content"] == b"video-bytes"
    assert seen["path"].name == f"{asset.id}.mp4"
    assert seen["path"].parent != canary.parent


async def test_extract_frames_task_never_writes_outside_its_temporary_directory(client, db_session, register_payload, monkeypatch, tmp_path):
    from api.tasks import media as media_tasks

    _token, org_id = await _owner_and_org(client, register_payload)
    canary = tmp_path / "task-canary.mp4"
    asset = await _hostile_video_asset(db_session, org_id, str(canary))
    asset.status = MediaStatus.completed
    await db_session.commit()
    seen = {}

    async def fake_extract_frames(db, a, video_path):
        seen["path"] = Path(video_path)

    class _Engine:
        async def dispose(self):
            return None

    @asynccontextmanager
    async def _session():
        yield db_session

    monkeypatch.setattr(media_tasks, "_session_factory", lambda: (_Engine(), _session))
    monkeypatch.setattr("api.services.document_storage.download_document_file", lambda key: b"video-bytes")
    monkeypatch.setattr("api.services.media.extract_video_frames", fake_extract_frames)

    assert await media_tasks._extract_frames_async() == 1
    assert not canary.exists()
    assert seen["path"].name == f"{asset.id}.mp4"


async def test_content_disposition_cannot_be_broken_out_of(client, db_session, register_payload, monkeypatch):
    token, org_id = await _owner_and_org(client, register_payload)
    asset = await _hostile_video_asset(db_session, org_id, 'evil"; filename*=UTF-8\'\'x.exe; .mp4')
    monkeypatch.setattr("api.routers.media.stream_document_file", lambda key: iter([b"data"]))

    response = await client.get(f"/media/{asset.id}/file", headers=_auth(token))

    assert response.status_code == 200
    disposition = response.headers["content-disposition"]
    assert disposition.count('"') == 2
    assert "filename*" not in disposition

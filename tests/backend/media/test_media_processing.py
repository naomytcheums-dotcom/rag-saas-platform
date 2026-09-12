"""Partie 22 -- real processing: image (OCR + vision description +
object tagging), audio (transcription), video (ffmpeg audio-extraction
+ transcription + frame-extraction + description + summary), and RAG
indexing of the real, resulting text. `litellm.acompletion`/
`atranscription` are mocked (same real, documented exception as
tests/test_llm_providers.py's own docstring: real, paid third-party
APIs, no real secrets in this environment) -- OCR/ffmpeg are mocked at
the module boundary the exact same way tests/test_documents.py's own
`_stub_s3` mocks S3, since neither Tesseract nor ffmpeg is confirmed
installed on this session's own dev machine (api/services/ocr.py's own
docstring says as much for Tesseract already)."""

import uuid
from unittest.mock import AsyncMock

import pytest
from litellm.types.utils import Choices, Message, ModelResponse
from sqlalchemy import select

from api.config import settings
from api.models.document import DocumentChunk
from api.models.media import MediaAsset, MediaFrame, MediaStatus, MediaTranscript, MediaType
from api.models.user import User
from api.services import media as media_service


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client, db_session, email: str, password: str = "correct-horse-battery-staple"):
    payload = {"email": email, "password": password, "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email))
    return access_token, user


async def _make_org(client, db_session, register_payload, name):
    owner_token, _owner = await _register(client, db_session, register_payload["email"], register_payload["password"])
    org_id = (await client.post("/organizations", json={"name": name}, headers=_auth_header(owner_token))).json()["id"]
    return owner_token, org_id


def _real_completion_response(text: str) -> ModelResponse:
    message = Message(content=text, role="assistant")
    choice = Choices(message=message, index=0, finish_reason="stop")
    return ModelResponse(choices=[choice])


@pytest.fixture(autouse=True)
def _configure_vision_key(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-oai-test")
    # Real default STT_PROVIDER is "web_speech" (client-side only, see
    # api/services/voice.py's own docstring) -- these tests exercise
    # the real SERVER-side whisper path, same real override
    # tests/test_voice_providers.py itself uses.
    monkeypatch.setattr(settings, "STT_PROVIDER", "whisper")


async def _create_asset(db_session, organization_id, media_type: MediaType) -> MediaAsset:
    asset = MediaAsset(
        organization_id=organization_id, uploaded_by=None, media_type=media_type, status=MediaStatus.pending,
        filename=f"asset.{media_type.value}", file_key=f"media/{organization_id}/fake/asset.{media_type.value}",
        file_size=100, mime_type=f"{media_type.value}/mp4" if media_type == MediaType.video else f"{media_type.value}/mpeg",
    )
    db_session.add(asset)
    await db_session.flush()
    return asset


async def test_process_image_asset_runs_ocr_and_vision_description(client, db_session, register_payload, monkeypatch):
    _owner_token, org_id = await _make_org(client, db_session, register_payload, "Process Image Org")
    asset = await _create_asset(db_session, uuid.UUID(org_id), MediaType.image)
    await db_session.commit()

    monkeypatch.setattr("api.services.media.download_document_file", lambda file_key: b"fake-image-bytes")
    monkeypatch.setattr("api.services.media.ocr_image_bytes", lambda content, language=None: "Texte reconnu par OCR")

    import litellm

    mock_acompletion = AsyncMock(return_value=_real_completion_response(
        '{"description": "Une photo de test.", "objects": ["chaise", "table"], "tags": ["interieur"]}'
    ))
    monkeypatch.setattr(litellm, "acompletion", mock_acompletion)

    updated = await media_service.process_media_asset(db_session, asset.id)
    await db_session.commit()

    assert updated.status == MediaStatus.completed
    assert updated.ocr_text == "Texte reconnu par OCR"
    assert updated.description == "Une photo de test."
    assert updated.objects_json == ["chaise", "table"]

    chunks = (await db_session.execute(select(DocumentChunk).where(DocumentChunk.media_asset_id == asset.id))).scalars().all()
    assert len(chunks) >= 1
    assert all(chunk.document_id is None for chunk in chunks)
    assert all(chunk.organization_id == uuid.UUID(org_id) for chunk in chunks)


async def test_process_image_asset_degrades_gracefully_without_ocr(client, db_session, register_payload, monkeypatch):
    from api.services.ocr import OCRNotAvailableError

    _owner_token, org_id = await _make_org(client, db_session, register_payload, "No OCR Org")
    asset = await _create_asset(db_session, uuid.UUID(org_id), MediaType.image)
    await db_session.commit()

    monkeypatch.setattr("api.services.media.download_document_file", lambda file_key: b"fake-image-bytes")

    def _raise_ocr_unavailable(content, language=None):
        raise OCRNotAvailableError("tesseract not installed")

    monkeypatch.setattr("api.services.media.ocr_image_bytes", _raise_ocr_unavailable)

    import litellm

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_completion_response('{"description": "ok", "objects": [], "tags": []}')))

    updated = await media_service.process_media_asset(db_session, asset.id)
    await db_session.commit()

    # A missing OCR binary must never fail the whole asset -- same real
    # degradation OCR already gets inside document processing.
    assert updated.status == MediaStatus.completed
    assert updated.ocr_text is None


async def test_process_audio_asset_transcribes_and_indexes(client, db_session, register_payload, monkeypatch):
    _owner_token, org_id = await _make_org(client, db_session, register_payload, "Process Audio Org")
    asset = await _create_asset(db_session, uuid.UUID(org_id), MediaType.audio)
    await db_session.commit()

    monkeypatch.setattr("api.services.media.download_document_file", lambda file_key: b"fake-audio-bytes")

    import litellm

    monkeypatch.setattr(litellm, "atranscription", AsyncMock(return_value=type("R", (), {"text": "Ceci est une transcription reelle."})()))

    updated = await media_service.process_media_asset(db_session, asset.id)
    await db_session.commit()

    assert updated.status == MediaStatus.completed
    transcript = (await db_session.execute(select(MediaTranscript).where(MediaTranscript.media_asset_id == asset.id))).scalars().first()
    assert transcript is not None
    assert transcript.text == "Ceci est une transcription reelle."

    chunks = (await db_session.execute(select(DocumentChunk).where(DocumentChunk.media_asset_id == asset.id))).scalars().all()
    assert any((c.metadata_json or {}).get("source") == "media_transcript" for c in chunks)


async def test_process_video_asset_extracts_audio_and_frames(client, db_session, register_payload, monkeypatch):
    _owner_token, org_id = await _make_org(client, db_session, register_payload, "Process Video Org")
    asset = await _create_asset(db_session, uuid.UUID(org_id), MediaType.video)
    await db_session.commit()

    monkeypatch.setattr("api.services.media.download_document_file", lambda file_key: b"fake-video-bytes")
    monkeypatch.setattr("api.services.media.get_video_duration_ms", lambda video_path: 12345)
    monkeypatch.setattr("api.services.media.extract_audio_from_video", lambda video_path: b"fake-wav-bytes")
    monkeypatch.setattr("api.services.media.upload_media_file", lambda org_id, asset_id, filename, content, mime_type: f"media/{org_id}/{asset_id}/{filename}")
    monkeypatch.setattr(
        "api.services.media.extract_frames",
        lambda video_path, interval_seconds, max_frames: [(0, b"frame0"), (5000, b"frame1")],
    )

    import litellm

    monkeypatch.setattr(litellm, "atranscription", AsyncMock(return_value=type("R", (), {"text": "Audio de la video."})()))
    # 2 real calls describe each real extracted frame (JSON), the 3rd
    # real call summarizes them into a real, plain-text video summary
    # (describe_video's own real prompt asks for prose, not JSON) --
    # side_effect gives each of the 3 real chat_completion calls its
    # own real, distinct response.
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(side_effect=[
        _real_completion_response('{"description": "Une scene.", "objects": ["personne"], "tags": []}'),
        _real_completion_response('{"description": "Une scene.", "objects": ["personne"], "tags": []}'),
        _real_completion_response("Une video montrant une personne dans une scene."),
    ]))

    updated = await media_service.process_media_asset(db_session, asset.id)
    await db_session.commit()

    assert updated.status == MediaStatus.completed
    assert updated.duration_ms == 12345

    transcript = (await db_session.execute(select(MediaTranscript).where(MediaTranscript.media_asset_id == asset.id))).scalars().first()
    assert transcript.text == "Audio de la video."

    frames = (await db_session.execute(select(MediaFrame).where(MediaFrame.media_asset_id == asset.id))).scalars().all()
    assert len(frames) == 2
    assert all(f.description == "Une scene." for f in frames)
    assert updated.description == "Une video montrant une personne dans une scene."


async def test_process_media_marks_failed_on_real_error(client, db_session, register_payload, monkeypatch):
    _owner_token, org_id = await _make_org(client, db_session, register_payload, "Fail Org")
    asset = await _create_asset(db_session, uuid.UUID(org_id), MediaType.image)
    await db_session.commit()

    def _raise(file_key):
        raise RuntimeError("real S3 outage")

    monkeypatch.setattr("api.services.media.download_document_file", _raise)

    updated = await media_service.process_media_asset(db_session, asset.id)
    await db_session.commit()

    assert updated.status == MediaStatus.failed
    assert "real S3 outage" in updated.error

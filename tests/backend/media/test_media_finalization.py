"""Partie 22 finalization -- real diarization (Deepgram-only, best-effort
parsing), real vision description wired into `process_document`'s own
embedded-image loop (off by default), real local YOLO object detection
now wired ahead of the vision-LLM's own objects in the media pipeline
(see tests/backend/media/test_object_detection.py for the detector
itself), and the deliberate, documented decision NOT to split frontend
components further (see docs/CAHIER_DES_CHARGES.md's own PARTIE 22
finalization note)."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from litellm.types.utils import Choices, Message, ModelResponse
from sqlalchemy import select

from api.config import settings
from api.models.media import MediaAsset, MediaStatus, MediaType
from api.services import media as media_service
from api.services.voice import VoiceError, _parse_diarization_segments, transcribe_audio_with_diarization


def _real_completion_response(text: str) -> ModelResponse:
    message = Message(content=text, role="assistant")
    choice = Choices(message=message, index=0, finish_reason="stop")
    return ModelResponse(choices=[choice])


class _FakeTranscription:
    def __init__(self, text: str, words=None):
        self.text = text
        if words is not None:
            self.words = words


# -------------------------------------------------------------- diarization

def test_parse_diarization_segments_extracts_real_speaker_words():
    response = _FakeTranscription("bonjour tout le monde", words=[
        {"word": "bonjour", "start": 0.0, "end": 0.4, "speaker": 0},
        {"word": "tout", "start": 0.5, "end": 0.7, "speaker": 1},
    ])
    segments = _parse_diarization_segments(response)
    assert segments == [
        {"speaker": 0, "start_ms": 0, "end_ms": 400, "text": "bonjour"},
        {"speaker": 1, "start_ms": 500, "end_ms": 700, "text": "tout"},
    ]


def test_parse_diarization_segments_returns_none_without_a_real_words_field():
    assert _parse_diarization_segments(_FakeTranscription("no words attribute at all")) is None


def test_parse_diarization_segments_returns_none_when_words_lack_speaker():
    response = _FakeTranscription("x", words=[{"word": "x", "start": 0.0, "end": 0.1}])
    assert _parse_diarization_segments(response) is None


async def test_transcribe_audio_with_diarization_requires_deepgram_key(monkeypatch):
    monkeypatch.setattr(settings, "DEEPGRAM_API_KEY", "")
    with pytest.raises(VoiceError):
        await transcribe_audio_with_diarization(b"fake-audio")


async def test_transcribe_audio_with_diarization_passes_diarize_true_to_litellm(monkeypatch):
    monkeypatch.setattr(settings, "DEEPGRAM_API_KEY", "dg-test")
    import litellm

    mock_atranscription = AsyncMock(return_value=_FakeTranscription("bonjour", words=[{"word": "bonjour", "start": 0.0, "end": 0.4, "speaker": 0}]))
    monkeypatch.setattr(litellm, "atranscription", mock_atranscription)

    text, segments = await transcribe_audio_with_diarization(b"fake-audio")

    assert text == "bonjour"
    assert segments == [{"speaker": 0, "start_ms": 0, "end_ms": 400, "text": "bonjour"}]
    assert mock_atranscription.call_args.kwargs["diarize"] is True


# -------------------------------------------------------------- vision wiring in process_document

async def test_describe_embedded_image_is_off_by_default(monkeypatch):
    from api.security.documents import describe_embedded_image_if_enabled

    monkeypatch.setattr(settings, "MULTIMODAL_ENABLED", True)
    monkeypatch.setattr(settings, "MULTIMODAL_DESCRIBE_DOCUMENT_IMAGES", False)

    description, objects = await describe_embedded_image_if_enabled(b"fake-image-bytes", "image/png", 0, "doc-1")
    assert (description, objects) == (None, None)


async def test_describe_embedded_image_calls_the_real_vision_pipeline_when_enabled(monkeypatch):
    from api.security.documents import describe_embedded_image_if_enabled

    monkeypatch.setattr(settings, "MULTIMODAL_ENABLED", True)
    monkeypatch.setattr(settings, "MULTIMODAL_DESCRIBE_DOCUMENT_IMAGES", True)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-oai-test")

    import litellm

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_completion_response(
        '{"description": "Un schema technique.", "objects": ["diagramme"], "tags": []}'
    )))

    description, objects = await describe_embedded_image_if_enabled(b"fake-image-bytes", "image/png", 0, "doc-1")
    assert description == "Un schema technique."
    assert objects == ["diagramme"]


async def test_describe_embedded_image_degrades_gracefully_on_a_real_provider_failure(monkeypatch):
    from api.security.documents import describe_embedded_image_if_enabled

    monkeypatch.setattr(settings, "MULTIMODAL_ENABLED", True)
    monkeypatch.setattr(settings, "MULTIMODAL_DESCRIBE_DOCUMENT_IMAGES", True)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-oai-test")

    import litellm

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(side_effect=RuntimeError("real provider outage")))

    description, objects = await describe_embedded_image_if_enabled(b"fake-image-bytes", "image/png", 0, "doc-1")
    # A real vision-provider failure must never propagate and abort
    # the whole document -- same degradation as OCR's own
    # OCRNotAvailableError handling right above it in the same loop.
    assert (description, objects) == (None, None)


# -------------------------------------------------------------- YOLO wired ahead of vision-LLM objects

async def _create_image_asset(db_session, organization_id) -> MediaAsset:
    asset = MediaAsset(
        organization_id=organization_id, uploaded_by=None, media_type=MediaType.image, status=MediaStatus.pending,
        filename="asset.png", file_key=f"media/{organization_id}/fake/asset.png", file_size=100, mime_type="image/png",
    )
    db_session.add(asset)
    await db_session.flush()
    return asset


async def _make_org_id(client, db_session, register_payload) -> uuid.UUID:
    payload = {"email": register_payload["email"], "password": register_payload["password"], "accept_terms": True}
    access_token = (await client.post("/auth/register", json=payload)).json()["access_token"]
    org_id = (await client.post("/organizations", json={"name": "YOLO Org"}, headers={"Authorization": f"Bearer {access_token}"})).json()["id"]
    return uuid.UUID(org_id)


async def test_process_media_asset_prefers_real_yolo_objects_over_vision_llm_objects(client, db_session, register_payload, monkeypatch):
    org_id = await _make_org_id(client, db_session, register_payload)
    asset = await _create_image_asset(db_session, org_id)
    await db_session.commit()

    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-oai-test")
    monkeypatch.setattr("api.services.media.download_document_file", lambda file_key: b"fake-image-bytes")
    monkeypatch.setattr("api.services.media.ocr_image_bytes", lambda content, language=None: "")

    import litellm

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_completion_response(
        '{"description": "Une photo.", "objects": ["objet-du-llm"], "tags": []}'
    )))

    with patch("api.services.object_detection.detect_objects_yolo", return_value=["person", "bus"]):
        updated = await media_service.process_media_asset(db_session, asset.id)
        await db_session.commit()

    assert updated.status == MediaStatus.completed
    # YOLO's own real objects win over the vision-LLM's own list when
    # YOLO is available -- the whole point of preferring the local,
    # dedicated detector.
    assert updated.objects_json == ["person", "bus"]
    assert updated.description == "Une photo."  # description still always comes from the vision LLM -- YOLO has no captioning ability


async def test_process_media_asset_falls_back_to_vision_llm_objects_when_yolo_unavailable(client, db_session, register_payload, monkeypatch):
    org_id = await _make_org_id(client, db_session, register_payload)
    asset = await _create_image_asset(db_session, org_id)
    await db_session.commit()

    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-oai-test")
    monkeypatch.setattr("api.services.media.download_document_file", lambda file_key: b"fake-image-bytes")
    monkeypatch.setattr("api.services.media.ocr_image_bytes", lambda content, language=None: "")

    import litellm

    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=_real_completion_response(
        '{"description": "Une photo.", "objects": ["objet-du-llm"], "tags": []}'
    )))

    from api.services.object_detection import YOLONotAvailableError

    with patch("api.services.object_detection.detect_objects_yolo", side_effect=YOLONotAvailableError("simulated: no real weights available")):
        updated = await media_service.process_media_asset(db_session, asset.id)
        await db_session.commit()

    assert updated.status == MediaStatus.completed
    assert updated.objects_json == ["objet-du-llm"]

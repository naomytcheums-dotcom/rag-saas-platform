"""Partie 22 finalization -- real diarization (Deepgram-only, best-effort
parsing), real vision description wired into `process_document`'s own
embedded-image loop (off by default), and the deliberate, documented
decision NOT to add a separate object detector or split components
further (see docs/CAHIER_DES_CHARGES.md's own PARTIE 22 finalization
note)."""

from unittest.mock import AsyncMock

import pytest
from litellm.types.utils import Choices, Message, ModelResponse

from api.config import settings
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

"""Deepgram requests that name a language (found by tests/contracts/test_voice_contract.py): LiteLLM dropped `language` from the Deepgram query string, so the language
a user chose never reached the vendor. These requests now go to /listen directly. Against a local FAKE Deepgram, not the real service."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vendor_fakes import FakeVendor, Resp, closed_url  # noqa: E402

from api.config import settings  # noqa: E402
from api.services.voice import VoiceError, transcribe_audio, transcribe_audio_with_diarization  # noqa: E402

BODY = {"results": {"channels": [{"alternatives": [{"transcript": "bonjour a tous", "words": [
    {"word": "bonjour", "punctuated_word": "Bonjour", "start": 0.0, "end": 0.4, "speaker": 0},
    {"word": "a", "start": 0.5, "end": 0.6, "speaker": 1},
    {"word": "tous", "start": 0.7, "end": 0.9, "speaker": 1}]}]}]}}


@pytest.fixture
def vendor(monkeypatch):
    monkeypatch.setattr(settings, "DEEPGRAM_API_KEY", "dg-language-key")
    with FakeVendor() as fake:
        fake.on("POST", "/listen", Resp(200, BODY))
        yield fake


async def test_the_chosen_language_reaches_deepgram_with_the_token_and_the_audio(vendor):
    assert await transcribe_audio(b"RIFFxxxxWAVE", provider="deepgram", language="fr", api_base=vendor.url) == "bonjour a tous"

    request = vendor.requests[0]
    assert request.query["language"] == ["fr"] and request.query["model"] == ["nova-2"] and "diarize" not in request.query
    assert request.headers["authorization"] == "Token dg-language-key" and request.body == b"RIFFxxxxWAVE"


async def test_language_and_diarization_are_both_sent_and_segments_carry_the_speakers(vendor):
    text, segments = await transcribe_audio_with_diarization(b"RIFFxxxxWAVE", language="fr", api_base=vendor.url)

    query = vendor.requests[0].query
    assert query["language"] == ["fr"] and query["diarize"] == ["true"]
    assert text == "bonjour a tous"
    assert [(s["speaker"], s["text"]) for s in segments] == [(0, "bonjour"), (1, "a"), (1, "tous")]
    assert segments[0]["start_ms"] == 0 and segments[2]["end_ms"] == 900


@pytest.mark.parametrize(("status", "expected"), [(401, "rejected the API key"), (403, "rejected the API key"), (429, "rate limiting"), (503, "HTTP 503")])
async def test_vendor_errors_become_voice_errors(vendor, status, expected):
    vendor._routes.clear()
    vendor.on("POST", "/listen", Resp(status, {"err_msg": "no"}))

    with pytest.raises(VoiceError, match=expected):
        await transcribe_audio(b"x", provider="deepgram", language="fr", api_base=vendor.url)


async def test_an_unreachable_vendor_and_an_unexpected_body_are_voice_errors(vendor):
    with pytest.raises(VoiceError, match="Deepgram transcription failed"):
        await transcribe_audio(b"x", provider="deepgram", language="fr", api_base=closed_url())
    vendor._routes.clear()
    vendor.on("POST", "/listen", Resp(200, {"results": {}}))
    with pytest.raises(VoiceError, match="unexpected response shape"):
        await transcribe_audio(b"x", provider="deepgram", language="fr", api_base=vendor.url)


async def test_without_a_language_the_request_still_goes_through_litellm(vendor):
    vendor._routes.clear()
    vendor.on("POST", "/listen", Resp(200, {"metadata": {"request_id": "r", "duration": 0.2, "channels": 1}, "results": {"channels": [{"alternatives": [{"transcript": "hello", "words": [{"word": "hello", "start": 0.0, "end": 0.2}]}]}]}}))

    assert await transcribe_audio(b"x", provider="deepgram", api_base=vendor.url) == "hello"
    assert "language" not in vendor.requests[0].query

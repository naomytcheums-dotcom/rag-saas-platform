"""Specs 8.2.2 text-to-speech, 8.2.3 real-time voice playback (server side), 8.2.5 voice activity detection (server side) + STT providers.

- Hosted vendors (ElevenLabs, Google Cloud TTS, OpenAI Whisper, Deepgram): CONTRACT tests against LOCAL FAKE servers; the vendor is fake, the product code
  and HTTP client are real. Real validation: scripts/validate_voice_live.py.
- Local, truly real: real speech rendered by the Windows speech engine (SAPI) -> the product's local Whisper (faster-whisper, real model) and the Silero VAD
  that ships with it. Skipped where SAPI or the cached model is missing.
"""

import base64
import os

import pytest

from api.config import settings
from api.services import voice
from api.services.voice import VoiceError, synthesize_speech, synthesize_with_elevenlabs, synthesize_with_google_cloud, transcribe_audio
from speech_samples import read_wav, room_noise, sapi_available, silence, synthesize_wav, tone, write_wav
from vendor_fakes import FakeVendor, Resp, closed_url

MP3_BYTES = b"ID3\x03\x00\x00\x00\x00\x00\x00" + os.urandom(64)


@pytest.fixture(autouse=True)
def _no_wait(monkeypatch):
    import asyncio

    async def instant(_):
        return None

    monkeypatch.setattr(voice.asyncio, "sleep", instant)
    monkeypatch.setattr(settings, "ELEVENLABS_API_KEY", "xi-contract-key")
    monkeypatch.setattr(settings, "GOOGLE_CLOUD_TTS_API_KEY", "goog-contract-key")
    assert asyncio


@pytest.fixture
def eleven(monkeypatch):
    with FakeVendor() as fake:
        monkeypatch.setattr(voice, "_ELEVENLABS_BASE_URL", f"{fake.url}/v1")
        yield fake


@pytest.fixture
def google(monkeypatch):
    with FakeVendor() as fake:
        monkeypatch.setattr(voice, "_GOOGLE_TTS_URL", f"{fake.url}/v1/text:synthesize")
        yield fake


# ------------------------------------------------------------------------------------------------------------------------- ElevenLabs TTS


async def test_elevenlabs_request_shape_and_audio_bytes(eleven):
    eleven.on("POST", "/v1/text-to-speech/*", Resp(200, MP3_BYTES, headers={"Content-Type": "audio/mpeg"}))
    audio = await synthesize_with_elevenlabs("Bonjour le monde", voice_id="21m00Tcm4TlvDq8ikWAM", speed=0.9, pitch=0.4)
    assert audio == MP3_BYTES
    (request,) = eleven.requests
    assert request.path == "/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM" and request.headers["xi-api-key"] == "xi-contract-key"
    assert request.json() == {"text": "Bonjour le monde", "model_id": settings.ELEVENLABS_MODEL, "voice_settings": {"stability": 0.4, "similarity_boost": 0.9}}


async def test_elevenlabs_default_voice_and_escaped_voice_id(eleven):
    eleven.on("POST", "/v1/text-to-speech/*", Resp(200, MP3_BYTES))
    await synthesize_with_elevenlabs("hi")
    await synthesize_with_elevenlabs("hi", voice_id="../voices?x=1")
    assert eleven.requests[0].path.endswith("/21m00Tcm4TlvDq8ikWAM")  # Rachel, the configured default
    assert eleven.requests[1].path == "/v1/text-to-speech/..%2Fvoices%3Fx%3D1"  # an id cannot redirect the request to another route


async def test_elevenlabs_errors_are_typed(eleven, monkeypatch):
    eleven.on("POST", "/v1/text-to-speech/*", Resp(401, {"detail": {"status": "invalid_api_key", "message": "Invalid API key"}}))
    with pytest.raises(VoiceError, match="401.*Invalid API key"):
        await synthesize_with_elevenlabs("hi")
    assert len(eleven.requests) == 1  # a billed call is not repeated
    eleven._routes.clear()
    eleven.on("POST", "/v1/text-to-speech/*", Resp(422, {"detail": [{"msg": "text too long"}]}))
    with pytest.raises(VoiceError, match="422"):
        await synthesize_with_elevenlabs("hi")
    eleven._routes.clear()
    eleven.on("POST", "/v1/text-to-speech/*", Resp(200, b""))
    with pytest.raises(VoiceError, match="empty"):
        await synthesize_with_elevenlabs("hi")
    monkeypatch.setattr(settings, "ELEVENLABS_API_KEY", "")
    with pytest.raises(VoiceError, match="not configured"):
        await synthesize_with_elevenlabs("hi")


async def test_elevenlabs_concurrency_limit_is_retried_once_but_5xx_is_not(eleven):
    eleven.on("POST", "/v1/text-to-speech/*", [Resp(429, {"detail": {"status": "too_many_concurrent_requests"}}, headers={"Retry-After": "2"}), Resp(200, MP3_BYTES)])
    assert await synthesize_with_elevenlabs("hi") == MP3_BYTES and len(eleven.requests) == 2
    eleven._routes.clear()
    eleven.requests.clear()
    eleven.on("POST", "/v1/text-to-speech/*", Resp(503, {"detail": "unavailable"}))
    with pytest.raises(VoiceError, match="503"):
        await synthesize_with_elevenlabs("hi")
    assert len(eleven.requests) == 1


async def test_elevenlabs_timeout_and_outage_are_typed(eleven, monkeypatch):
    monkeypatch.setattr(voice, "_TTS_TIMEOUT_SECONDS", 0.3)
    eleven.on("POST", "/v1/text-to-speech/*", Resp(200, MP3_BYTES, delay=1.5))
    with pytest.raises(VoiceError, match="did not answer"):
        await synthesize_with_elevenlabs("hi")
    monkeypatch.setattr(voice, "_TTS_TIMEOUT_SECONDS", 5.0)
    monkeypatch.setattr(voice, "_ELEVENLABS_BASE_URL", f"{closed_url()}/v1")
    with pytest.raises(VoiceError, match="could not be reached"):
        await synthesize_with_elevenlabs("hi")


async def test_elevenlabs_voice_catalog_is_requested_with_the_key(eleven, monkeypatch):
    eleven.on("GET", "/v1/voices", Resp(200, {"voices": [{"name": "Zed", "voice_id": "v1", "labels": {"gender": "male"}, "preview_url": "https://x/p.mp3"}]}))
    monkeypatch.setattr(voice.httpx, "get", lambda url, **kw: __import__("httpx").Client().get(url, **kw))
    voices = voice.get_elevenlabs_voices()
    assert voices == [{"name": "Zed", "voice_id": "v1", "gender": "male", "preview_url": "https://x/p.mp3", "source": "live"}]
    assert eleven.requests[0].headers["xi-api-key"] == "xi-contract-key"


# ------------------------------------------------------------------------------------------------------------------------- Google Cloud TTS


async def test_google_tts_request_shape_and_base64_audio(google):
    google.on("POST", "/v1/text:synthesize", Resp(200, {"audioContent": base64.b64encode(MP3_BYTES).decode()}))
    audio = await synthesize_with_google_cloud("Bonjour", voice_id="fr-FR-Neural2-A", speed=1.2, pitch=-2.0)
    assert audio == MP3_BYTES
    (request,) = google.requests
    assert request.headers["x-goog-api-key"] == "goog-contract-key" and "key" not in request.query  # the key is not in the URL (it would be logged)
    assert request.json() == {"input": {"text": "Bonjour"}, "voice": {"name": "fr-FR-Neural2-A", "languageCode": "fr-FR"},
                              "audioConfig": {"audioEncoding": "MP3", "speakingRate": 1.2, "pitch": -2.0}}


async def test_google_tts_clamps_rate_and_pitch_to_the_ranges_google_accepts(google):
    google.on("POST", "/v1/text:synthesize", Resp(200, {"audioContent": base64.b64encode(MP3_BYTES).decode()}))
    await synthesize_with_google_cloud("x", speed=99, pitch=-99)
    assert google.requests[0].json()["audioConfig"] == {"audioEncoding": "MP3", "speakingRate": 4.0, "pitch": -20.0}


async def test_google_tts_errors_are_typed(google, monkeypatch):
    google.on("POST", "/v1/text:synthesize", Resp(400, {"error": {"code": 400, "message": "API key not valid. Please pass a valid API key.", "status": "INVALID_ARGUMENT"}}))
    with pytest.raises(VoiceError, match="400.*API key not valid"):
        await synthesize_with_google_cloud("x")
    google._routes.clear()
    google.on("POST", "/v1/text:synthesize", Resp(200, {"unexpected": True}))
    with pytest.raises(VoiceError, match="no audioContent"):
        await synthesize_with_google_cloud("x")
    google._routes.clear()
    google.on("POST", "/v1/text:synthesize", [Resp(429, {"error": {"message": "Quota exceeded"}}, headers={"Retry-After": "1"}), Resp(200, {"audioContent": base64.b64encode(MP3_BYTES).decode()})])
    assert await synthesize_with_google_cloud("x") == MP3_BYTES
    monkeypatch.setattr(settings, "GOOGLE_CLOUD_TTS_API_KEY", None)
    with pytest.raises(VoiceError, match="not configured"):
        await synthesize_with_google_cloud("x")


async def test_provider_dispatch(eleven, google, monkeypatch):
    eleven.on("POST", "/v1/text-to-speech/*", Resp(200, b"ELEVEN"))
    google.on("POST", "/v1/text:synthesize", Resp(200, {"audioContent": base64.b64encode(b"GOOGLE").decode()}))
    monkeypatch.setattr(settings, "TTS_PROVIDER", "google_cloud")
    assert await synthesize_speech("x") == b"GOOGLE"
    assert await synthesize_speech("x", provider="elevenlabs") == b"ELEVEN"
    monkeypatch.setattr(settings, "TTS_PROVIDER", "web_speech")  # browser-only: the server falls back to the hosted default
    assert await synthesize_speech("x") == b"ELEVEN"
    with pytest.raises(VoiceError, match="no server-side synthesis"):
        await synthesize_speech("x", provider="web_speech")


async def test_tts_endpoint_over_http(client, register_payload, eleven, google, monkeypatch):
    eleven.on("POST", "/v1/text-to-speech/*", Resp(200, MP3_BYTES))
    google.on("POST", "/v1/text:synthesize", Resp(200, {"audioContent": base64.b64encode(b"GOOGLE-AUDIO").decode()}))
    assert (await client.post("/voice/tts", json={"text": "hello"})).status_code in (401, 403)
    token = (await client.post("/auth/register", json={**register_payload, "accept_terms": True})).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    ok = await client.post("/voice/tts", json={"text": "hello"}, headers=headers)
    assert ok.status_code == 200 and ok.headers["content-type"] == "audio/mpeg" and ok.content == MP3_BYTES
    viag = await client.post("/voice/tts", json={"text": "hello", "provider": "google_cloud"}, headers=headers)
    assert viag.status_code == 200 and viag.content == b"GOOGLE-AUDIO"
    assert (await client.post("/voice/tts", json={"text": "x" * 5001}, headers=headers)).status_code == 422  # billed per character: bounded
    assert (await client.post("/voice/tts", json={"text": ""}, headers=headers)).status_code == 422
    assert (await client.post("/voice/tts", json={"text": "hi", "provider": "web_speech"}, headers=headers)).status_code == 422
    monkeypatch.setattr(settings, "ELEVENLABS_API_KEY", "")
    assert (await client.post("/voice/tts", json={"text": "hi"}, headers=headers)).status_code == 400  # vendor errors are 400s with a message, never a 500
    eleven._routes.clear()
    eleven.on("POST", "/v1/text-to-speech/*", Resp(401, {"detail": {"message": "Invalid API key"}}))
    monkeypatch.setattr(settings, "ELEVENLABS_API_KEY", "bad")
    bad = await client.post("/voice/tts", json={"text": "hi"}, headers=headers)
    assert bad.status_code == 400 and "Invalid API key" in bad.json()["detail"]


# ------------------------------------------------------------------------------------------------------------------------- hosted STT


@pytest.fixture
def stt_vendor():
    with FakeVendor() as fake:
        yield fake


async def test_whisper_request_shape_and_text(stt_vendor, monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-whisper-contract")
    stt_vendor.on("POST", "/audio/transcriptions", Resp(200, {"text": "the invoice is due"}))
    text = await transcribe_audio(b"RIFF....WAVEfmt ", filename="clip.wav", provider="whisper", language="en", api_base=stt_vendor.url)
    assert text == "the invoice is due"
    request = stt_vendor.requests[0]
    assert request.headers["authorization"] == "Bearer sk-whisper-contract" and request.headers["content-type"].startswith("multipart/form-data")
    assert b'name="model"\r\n\r\nwhisper-1' in request.body and b'filename="clip.wav"' in request.body and b'name="language"\r\n\r\nen' in request.body


async def test_whisper_failures_are_voice_errors_not_raw_exceptions(stt_vendor, monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-whisper-contract")
    stt_vendor.on("POST", "/audio/transcriptions", Resp(401, {"error": {"message": "Incorrect API key provided", "type": "invalid_request_error"}}))
    with pytest.raises(VoiceError, match="rejected the API key"):
        await transcribe_audio(b"x", provider="whisper", api_base=stt_vendor.url)
    stt_vendor._routes.clear()
    stt_vendor.on("POST", "/audio/transcriptions", Resp(429, {"error": {"message": "Rate limit", "type": "rate_limit_error"}}, headers={"retry-after": "0"}))
    with pytest.raises(VoiceError, match="rate limiting"):
        await transcribe_audio(b"x", provider="whisper", api_base=stt_vendor.url)
    stt_vendor._routes.clear()
    stt_vendor.on("POST", "/audio/transcriptions", Resp(400, {"error": {"message": "Audio file might be corrupted or unsupported", "type": "invalid_request_error"}}))
    with pytest.raises(VoiceError, match="transcription failed"):
        await transcribe_audio(b"x", provider="whisper", api_base=stt_vendor.url)
    with pytest.raises(VoiceError):
        await transcribe_audio(b"x", provider="whisper", api_base=closed_url())


DEEPGRAM_BODY = {"metadata": {"request_id": "r", "duration": 1.2, "channels": 1}, "results": {"channels": [{"alternatives": [{
    "transcript": "hello there", "confidence": 0.99,
    "words": [{"word": "hello", "punctuated_word": "Hello", "start": 0.0, "end": 0.4, "speaker": 0}, {"word": "there", "punctuated_word": "there", "start": 0.5, "end": 0.9, "speaker": 1}]}]}]}}


async def test_deepgram_request_shape_text_and_diarization(stt_vendor, monkeypatch):
    monkeypatch.setattr(settings, "DEEPGRAM_API_KEY", "dg-contract-key")
    stt_vendor.on("POST", "/listen", Resp(200, DEEPGRAM_BODY))
    assert await transcribe_audio(b"RIFFxxxxWAVE", provider="deepgram", language="fr", api_base=stt_vendor.url) == "hello there"
    request = stt_vendor.requests[0]
    assert request.headers["authorization"] == "Token dg-contract-key" and request.body == b"RIFFxxxxWAVE"
    assert request.query["model"] == ["nova-2"] and request.query.get("language") == ["fr"], request.query  # the language the user chose must reach Deepgram
    text, segments = await voice.transcribe_audio_with_diarization(b"RIFFxxxxWAVE", api_base=stt_vendor.url)
    assert stt_vendor.requests[1].query["diarize"] == ["true"]
    assert text and (segments is None or {s["speaker"] for s in segments} == {0, 1})


async def test_deepgram_errors_are_voice_errors(stt_vendor, monkeypatch):
    monkeypatch.setattr(settings, "DEEPGRAM_API_KEY", "dg-contract-key")
    stt_vendor.on("POST", "/listen", Resp(401, {"err_code": "INVALID_AUTH", "err_msg": "Invalid credentials."}))
    with pytest.raises(VoiceError):
        await transcribe_audio(b"x", provider="deepgram", api_base=stt_vendor.url)
    stt_vendor._routes.clear()
    stt_vendor.on("POST", "/listen", Resp(503, {"err_msg": "unavailable"}))
    with pytest.raises(VoiceError):
        await transcribe_audio(b"x", provider="deepgram", api_base=stt_vendor.url)


# ------------------------------------------------------------------------------------------------------------------------- real, local speech


needs_sapi = pytest.mark.skipif(not sapi_available(), reason="Windows SAPI (pywin32) is needed to render real speech")


@pytest.fixture(scope="module")
def speech_wav(tmp_path_factory):
    return synthesize_wav("The invoice is due on the fifteenth of October.", str(tmp_path_factory.mktemp("speech") / "speech.wav"))


@pytest.fixture(scope="module")
def local_whisper_ready():
    if not voice.local_whisper_available():
        pytest.skip("faster-whisper is not installed")
    from huggingface_hub import try_to_load_from_cache  # noqa: F401

    return True


@needs_sapi
async def test_real_speech_is_transcribed_by_the_local_whisper(speech_wav, local_whisper_ready, monkeypatch):
    monkeypatch.setattr(settings, "STT_PROVIDER", "local_whisper")
    monkeypatch.setattr(settings, "LOCAL_WHISPER_MODEL", "base")
    text = await transcribe_audio(open(speech_wav, "rb").read(), filename="speech.wav", language="en")
    lowered = text.lower()
    assert "invoice" in lowered and "october" in lowered, text


@needs_sapi
async def test_silence_and_room_noise_produce_no_transcript(local_whisper_ready, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LOCAL_WHISPER_MODEL", "base")
    for name, samples in (("silence", silence(3)), ("noise", room_noise(3))):
        path = write_wav(str(tmp_path / f"{name}.wav"), samples)
        assert await voice.transcribe_local_whisper(open(path, "rb").read(), language="en") == "", name  # the VAD filter drops it before Whisper can hallucinate words


@needs_sapi
def test_silero_vad_finds_the_speech_in_real_speech_and_nothing_in_silence_noise_or_a_tone(speech_wav, tmp_path):
    """8.2.5 server side: the Silero VAD bundled with faster-whisper (what the product's local STT runs with vad_filter=True)."""
    from faster_whisper.vad import VadOptions, get_speech_timestamps
    import numpy as np

    def speech_seconds(samples, rate):
        audio = np.asarray(samples, dtype=np.float32)
        if rate != 16000:
            audio = np.interp(np.linspace(0, len(audio) - 1, int(len(audio) * 16000 / rate)), np.arange(len(audio)), audio).astype(np.float32)
        return sum(chunk["end"] - chunk["start"] for chunk in get_speech_timestamps(audio, VadOptions())) / 16000

    samples, rate = read_wav(speech_wav)
    duration = len(samples) / rate
    # leading and trailing pauses around the sentence: the VAD must find the sentence, not the pauses
    padded = silence(1.0) + [s for s in samples] + silence(1.0)
    padded_rate_fixed = speech_seconds(padded[: len(padded)], 16000) if rate == 16000 else None
    found = speech_seconds(samples, rate)
    assert 0.5 * duration < found <= duration + 0.5, (found, duration)
    assert speech_seconds(silence(3), 16000) == 0
    assert speech_seconds(room_noise(3), 16000) == 0
    assert speech_seconds(tone(3), 16000) < 0.5  # a steady beep is not speech
    assert padded_rate_fixed is None or padded_rate_fixed < duration + 1.0

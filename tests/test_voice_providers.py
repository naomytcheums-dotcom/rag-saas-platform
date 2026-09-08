"""Partie 8.2.1 (STT) + 8.2.2/8.2.9 (TTS / ElevenLabs)."""

from unittest.mock import AsyncMock, MagicMock, patch

import litellm
import pytest

from api.config import settings
from api.services.voice import (
    VoiceError, get_elevenlabs_voice, get_elevenlabs_voice_preview, get_elevenlabs_voices, synthesize_with_elevenlabs,
    transcribe_audio,
)


# --------------------------------------------------------------------- STT (8.2.1)


async def test_transcribe_audio_rejects_web_speech():
    """Validation criterion: web_speech n'a pas de contrepartie serveur."""
    with pytest.raises(VoiceError):
        await transcribe_audio(b"fake audio", provider="web_speech")


async def test_transcribe_audio_rejects_unknown_provider():
    with pytest.raises(VoiceError):
        await transcribe_audio(b"fake audio", provider="not-a-real-provider")


async def test_transcribe_audio_requires_openai_key_for_whisper(monkeypatch):
    """Validation criterion: robustesse -- clé API manquante."""
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    with pytest.raises(VoiceError):
        await transcribe_audio(b"fake audio", provider="whisper")


async def test_transcribe_audio_calls_litellm_atranscription(monkeypatch):
    """Validation criterion: la reconnaissance vocale fonctionne."""
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-test")
    mock_response = MagicMock(text="hello world")
    monkeypatch.setattr(litellm, "atranscription", AsyncMock(return_value=mock_response))

    text = await transcribe_audio(b"fake audio", provider="whisper")
    assert text == "hello world"


# ------------------------------------------------------------- TTS / ElevenLabs (8.2.2/8.2.9)


def test_get_elevenlabs_voices_falls_back_without_api_key(monkeypatch):
    """Validation criterion: robustesse -- API indisponible / pas de clé."""
    monkeypatch.setattr(settings, "ELEVENLABS_API_KEY", None)
    voices = get_elevenlabs_voices()
    assert len(voices) == 9
    assert all(v["source"] == "fallback" for v in voices)
    assert any(v["name"] == "Rachel" for v in voices)


def test_get_elevenlabs_voice_finds_by_id(monkeypatch):
    monkeypatch.setattr(settings, "ELEVENLABS_API_KEY", None)
    voice = get_elevenlabs_voice("21m00Tcm4TlvDq8ikWAM")
    assert voice is not None
    assert voice["name"] == "Rachel"


def test_get_elevenlabs_voice_preview_none_without_live_data(monkeypatch):
    monkeypatch.setattr(settings, "ELEVENLABS_API_KEY", None)
    assert get_elevenlabs_voice_preview("21m00Tcm4TlvDq8ikWAM") is None


async def test_synthesize_with_elevenlabs_requires_api_key(monkeypatch):
    """Validation criterion: robustesse -- pas de clé configurée."""
    monkeypatch.setattr(settings, "ELEVENLABS_API_KEY", None)
    with pytest.raises(VoiceError):
        await synthesize_with_elevenlabs("hello")


async def test_synthesize_with_elevenlabs_returns_audio_bytes(monkeypatch):
    """Validation criterion: la synthèse vocale fonctionne."""
    monkeypatch.setattr(settings, "ELEVENLABS_API_KEY", "sk-test")

    mock_response = MagicMock(status_code=200, content=b"fake-mp3-bytes")
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        audio = await synthesize_with_elevenlabs("hello", voice_id="21m00Tcm4TlvDq8ikWAM")

    assert audio == b"fake-mp3-bytes"


async def test_synthesize_with_elevenlabs_surfaces_api_error(monkeypatch):
    """Validation criterion: les erreurs sont gérées."""
    monkeypatch.setattr(settings, "ELEVENLABS_API_KEY", "sk-test")

    mock_response = MagicMock(status_code=401, text="unauthorized")
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(VoiceError):
            await synthesize_with_elevenlabs("hello")

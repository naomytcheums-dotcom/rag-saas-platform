"""Voice agent brick: open-source local STT provider + the `/voice/organizations/{org_id}/agent` turn.

Real here: provider routing, honest degradation when the optional package is absent, input bounds, injection-block mapping,
tenant isolation, auth, and the credit/spend gate at the endpoint. Not exercised here (needs a downloaded Whisper model and
real audio): the actual faster-whisper inference -- see docs/api/VOICE_AGENT.md."""

import types
import uuid

import pytest

from api.services import voice


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---- local_whisper provider -------------------------------------------------------------------------------------

async def test_local_whisper_without_the_package_fails_honestly_with_the_install_command(monkeypatch):
    monkeypatch.setattr(voice, "local_whisper_available", lambda: False)
    with pytest.raises(voice.VoiceError, match="pip install faster-whisper"):
        await voice.transcribe_audio(b"x", provider="local_whisper")


async def test_local_whisper_is_routed_by_transcribe_audio(monkeypatch):
    seen = {}

    async def fake_local(audio, *, language=None):
        seen.update(audio=audio, language=language)
        return "bonjour"

    monkeypatch.setattr(voice, "transcribe_local_whisper", fake_local)
    assert await voice.transcribe_audio(b"abc", provider="local_whisper", language="fr-FR") == "bonjour"
    assert seen == {"audio": b"abc", "language": "fr-FR"}


async def test_local_whisper_wraps_runtime_failures_in_voice_error(monkeypatch):
    monkeypatch.setattr(voice, "local_whisper_available", lambda: True)

    def boom(audio, language):
        raise RuntimeError("cannot decode")

    monkeypatch.setattr(voice, "_transcribe_local_sync", boom)
    with pytest.raises(voice.VoiceError, match="local transcription failed: RuntimeError"):
        await voice.transcribe_local_whisper(b"x")


def test_local_whisper_language_locale_is_reduced_to_a_code(monkeypatch):
    captured = {}

    class FakeModel:
        def transcribe(self, f, language=None, vad_filter=None):
            captured["language"] = language
            return [types.SimpleNamespace(text=" hello "), types.SimpleNamespace(text="world ")], None

    monkeypatch.setattr(voice, "_load_local_whisper", lambda: FakeModel())
    assert voice._transcribe_local_sync(b"x", "fr-FR") == "hello world"
    assert captured["language"] == "fr"
    voice._transcribe_local_sync(b"x", None)
    assert captured["language"] is None


# ---- voice_agent_turn ---------------------------------------------------------------------------------------------

def _patch_pipeline(monkeypatch, *, transcript="what is the refund policy", answer="30 days [1]"):
    calls = {}

    async def fake_stt(audio, **kw):
        calls["stt"] = kw
        return transcript

    async def fake_generate(db, org_id, query, **kw):
        calls["generate"] = (org_id, query, kw)
        return types.SimpleNamespace(id=uuid.uuid4(), answer=answer)

    async def fake_citations(db, response_id):
        return [types.SimpleNamespace(
            citation_number=1, chunk_id=uuid.uuid4(), document_id=uuid.uuid4(), source_title="Policy", source_url=None, document_name="policy.pdf",
        )]

    async def fake_tts(text, **kw):
        calls["tts"] = text
        return b"AUDIO"

    monkeypatch.setattr(voice, "transcribe_audio", fake_stt)
    monkeypatch.setattr("api.services.generation.generate_response", fake_generate)
    monkeypatch.setattr("api.services.citations.get_citations_by_response", fake_citations)
    monkeypatch.setattr(voice, "synthesize_with_elevenlabs", fake_tts)
    return calls


async def test_turn_runs_stt_then_rag_scoped_to_the_organization_and_returns_sources(monkeypatch):
    calls = _patch_pipeline(monkeypatch)
    org_id, user_id = uuid.uuid4(), uuid.uuid4()
    result = await voice.voice_agent_turn(None, org_id, b"audio", user_id=user_id)
    assert result["transcript"] == "what is the refund policy"
    assert calls["generate"][0] == org_id and calls["generate"][2]["created_by"] == user_id
    assert result["sources"][0]["source_title"] == "Policy" and result["sources"][0]["citation_number"] == 1
    assert isinstance(result["sources"][0]["chunk_id"], str)
    assert result["answer_audio"] is None and "tts" not in calls


async def test_turn_synthesizes_speech_only_when_asked(monkeypatch):
    calls = _patch_pipeline(monkeypatch)
    result = await voice.voice_agent_turn(None, uuid.uuid4(), b"audio", speak=True)
    assert result["answer_audio"] == b"AUDIO" and calls["tts"] == "30 days [1]"


async def test_turn_rejects_empty_and_oversized_audio_before_any_provider_call(monkeypatch):
    calls = _patch_pipeline(monkeypatch)
    monkeypatch.setattr(voice.settings, "VOICE_AGENT_MAX_AUDIO_BYTES", 10)
    with pytest.raises(voice.VoiceError, match="too large"):
        await voice.voice_agent_turn(None, uuid.uuid4(), b"x" * 11)
    with pytest.raises(voice.VoiceError, match="empty"):
        await voice.voice_agent_turn(None, uuid.uuid4(), b"")
    assert "stt" not in calls


async def test_turn_rejects_silence_and_bounds_the_transcript(monkeypatch):
    _patch_pipeline(monkeypatch, transcript="   ")
    with pytest.raises(voice.VoiceError, match="no speech"):
        await voice.voice_agent_turn(None, uuid.uuid4(), b"audio")
    calls = _patch_pipeline(monkeypatch, transcript="a" * 5000)
    monkeypatch.setattr(voice.settings, "VOICE_AGENT_MAX_TRANSCRIPT_CHARS", 100)
    await voice.voice_agent_turn(None, uuid.uuid4(), b"audio")
    assert len(calls["generate"][1]) == 100


async def test_a_spoken_injection_is_blocked_and_surfaces_as_voice_error(monkeypatch):
    from api.services.generation import GenerationBlockedError

    _patch_pipeline(monkeypatch)

    async def blocked(*a, **k):
        raise GenerationBlockedError("prompt injection detected")

    monkeypatch.setattr("api.services.generation.generate_response", blocked)
    with pytest.raises(voice.VoiceError, match="injection"):
        await voice.voice_agent_turn(None, uuid.uuid4(), b"audio")


# ---- endpoint -----------------------------------------------------------------------------------------------------

async def _org_with_owner(client, email, password):
    token = (await client.post("/auth/register", json={"email": email, "password": password, "accept_terms": True})).json()["access_token"]
    org_id = (await client.post("/organizations", json={"name": f"Voice {uuid.uuid4().hex[:6]}"}, headers=_auth(token))).json()["id"]
    return token, org_id


def _audio():
    return {"file": ("q.wav", b"RIFFfakewav", "audio/wav")}


async def test_endpoint_requires_authentication(client):
    response = await client.post(f"/voice/organizations/{uuid.uuid4()}/agent", files=_audio())
    assert response.status_code in (401, 403)


async def test_endpoint_is_closed_to_another_tenant(client, register_payload, monkeypatch):
    _patch_pipeline(monkeypatch)
    _, org_a = await _org_with_owner(client, register_payload["email"], register_payload["password"])
    token_b, _ = await _org_with_owner(client, f"voice-b-{uuid.uuid4().hex[:6]}@example.com", "correct-horse-battery-staple")
    response = await client.post(f"/voice/organizations/{org_a}/agent", files=_audio(), headers=_auth(token_b))
    assert response.status_code in (403, 404)


async def test_endpoint_without_credits_is_402_before_any_stt_call(client, register_payload, monkeypatch):
    from api.services.billing_credits import InsufficientCreditsError

    calls = _patch_pipeline(monkeypatch)
    token, org_id = await _org_with_owner(client, register_payload["email"], register_payload["password"])

    async def broke(*a, **k):
        raise InsufficientCreditsError("balance 0")

    monkeypatch.setattr("api.services.billing_credits.assert_org_can_spend", broke)
    response = await client.post(f"/voice/organizations/{org_id}/agent", files=_audio(), headers=_auth(token))
    assert response.status_code == 402
    assert "stt" not in calls


async def test_endpoint_happy_path_returns_answer_and_sources(client, register_payload, monkeypatch):
    _patch_pipeline(monkeypatch)
    token, org_id = await _org_with_owner(client, register_payload["email"], register_payload["password"])

    async def no_spend(*a, **k):
        return None

    monkeypatch.setattr("api.services.billing_credits.assert_org_can_spend", no_spend)
    response = await client.post(f"/voice/organizations/{org_id}/agent", files=_audio(), headers=_auth(token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["answer_text"] == "30 days [1]" and body["answer_audio_base64"] is None
    assert body["sources"][0]["document_name"] == "policy.pdf"


async def test_endpoint_maps_voice_errors_to_400(client, register_payload, monkeypatch):
    token, org_id = await _org_with_owner(client, register_payload["email"], register_payload["password"])

    async def no_spend(*a, **k):
        return None

    async def failing(*a, **k):
        raise voice.VoiceError("no speech detected in the audio")

    monkeypatch.setattr("api.services.billing_credits.assert_org_can_spend", no_spend)
    monkeypatch.setattr("api.routers.voice.voice_agent_turn", failing)
    response = await client.post(f"/voice/organizations/{org_id}/agent", files=_audio(), headers=_auth(token))
    assert response.status_code == 400 and "no speech" in response.json()["detail"]

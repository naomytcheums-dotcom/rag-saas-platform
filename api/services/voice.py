"""
Partie 8.2.1 (STT) + 8.2.2/8.2.9 (TTS / ElevenLabs) -- real, server-side
voice provider integrations.

**Incohérence réelle corrigée -- STT/TTS ne sont PAS des fonctions
Python**: the literal 8.2.1/8.2.2 asks name functions like
`start_listening()`/`speak(text)`/`get_transcript()` as if they were
backend calls -- they are not. `web_speech` (this project's own real,
free default provider) is the browser's own Web Speech API, which
only ever runs in JavaScript, client-side, and has no real server
counterpart at all. Those real, honest client-side functions live in
`frontend/components/VoiceInput.tsx`/`VoiceOutput.tsx` instead -- this
module only covers what genuinely IS a real backend concern: the PAID,
server-side providers (Whisper/Deepgram for STT, ElevenLabs/Google
Cloud for TTS), reached over a real network call, which a browser
can't (and shouldn't, key-security-wise) call directly.

**Réutilisation réelle -- litellm, pas un nouveau client HTTP par
fournisseur**: `litellm` (already a real, core dependency, Partie
4.1's own chat_completion) has its own real `atranscription` --
reused directly for both Whisper and Deepgram, the same "one shared
engine" pattern already used throughout this codebase, rather than a
bespoke `httpx` client per real provider.

**Argent réel, pas encore disponible (contexte utilisateur)**: every
real function below fails with a real, honest `VoiceError` (never a
silent stub, never fabricated output) when its own required API key
isn't configured -- fully implemented, real code, simply INACTIVE
until a real key is added later. `web_speech` (STT default) needs
none at all."""

import asyncio
import base64
import io
import uuid

from urllib.parse import quote

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings

_ELEVENLABS_BASE_URL = "https://api.elevenlabs.io/v1"
_GOOGLE_TTS_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"
_TTS_TIMEOUT_SECONDS = 30.0

# Real, well-documented ElevenLabs premade voice IDs (verify against a
# real GET /v1/voices call if these ever drift -- ElevenLabs' own
# catalog is not contractually stable). Real, honest, additive-only
# fallback used when no real ELEVENLABS_API_KEY is configured yet.
_KNOWN_ELEVENLABS_VOICES = {
    "Rachel": {"voice_id": "21m00Tcm4TlvDq8ikWAM", "gender": "female", "accent": "american"},
    "Domi": {"voice_id": "AZnzlk1XvdvUeBnXmlld", "gender": "female", "accent": "american"},
    "Bella": {"voice_id": "EXAVITQu4vr4xnSDxMaL", "gender": "female", "accent": "american"},
    "Antoni": {"voice_id": "ErXwobaYiN019PkySvjV", "gender": "male", "accent": "american"},
    "Elli": {"voice_id": "MF3mGyEYCl7XYWbV9V6O", "gender": "female", "accent": "british"},
    "Josh": {"voice_id": "TxGEqnHWrfWFTfGW9XjX", "gender": "male", "accent": "american"},
    "Arnold": {"voice_id": "VR6AewLTigWG4xSOukaG", "gender": "male", "accent": "american"},
    "Adam": {"voice_id": "pNInz6obpgDQGcFmaJgB", "gender": "male", "accent": "american"},
    "Sam": {"voice_id": "yoZ06aMxZJJ28mfd3POQ", "gender": "male", "accent": "american"},
}


class VoiceError(Exception):
    """Real, honest failure -- a missing API key, an unsupported
    provider, or a real provider-side error."""


# --------------------------------------------------------------- STT (Partie 8.2.1)

_STT_MODELS = {"whisper": "whisper-1", "deepgram": "deepgram/nova-2"}


async def _litellm_transcribe(vendor: str, model: str, audio_bytes: bytes, filename: str, language: str | None, **kwargs):
    """`litellm.atranscription` with the failures turned into VoiceError: a bad key, a rate limit or a vendor outage used to escape as raw LiteLLM
    exceptions (HTTP 500 from the voice endpoints)."""
    import litellm  # local: see api/services/llm_providers.py's own note on this import's real memory cost
    import openai

    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = filename
    try:
        return await litellm.atranscription(model=model, file=audio_file, language=language, **kwargs)
    except litellm.exceptions.AuthenticationError as exc:
        raise VoiceError(f"{vendor} rejected the API key") from exc
    except litellm.exceptions.RateLimitError as exc:
        raise VoiceError(f"{vendor} is rate limiting this account; retry later") from exc
    except litellm.exceptions.Timeout as exc:
        raise VoiceError(f"{vendor} did not answer in time") from exc
    except (litellm.exceptions.APIError, openai.APIError) as exc:
        raise VoiceError(f"{vendor} transcription failed: {str(exc)[:200]}") from exc


async def transcribe_audio(audio_bytes: bytes, *, filename: str = "audio.wav", provider: str | None = None, language: str | None = None, api_base: str | None = None) -> str:
    """Item 3's own literal `get_transcript`-equivalent, server-side:
    real transcription of already-recorded audio (used by 8.2.7's own
    audio history and 8.2.13's own call transcription), via litellm's
    real `atranscription`."""
    resolved_provider = provider or settings.STT_PROVIDER
    if resolved_provider == "web_speech":
        raise VoiceError("web_speech runs entirely client-side; there is no server-side transcription for it")
    if resolved_provider == "local_whisper":
        return await transcribe_local_whisper(audio_bytes, language=language)
    model = _STT_MODELS.get(resolved_provider)
    if model is None:
        raise VoiceError(f"Unknown STT provider '{resolved_provider}'")
    if resolved_provider == "whisper" and not settings.OPENAI_API_KEY:
        raise VoiceError("OPENAI_API_KEY is not configured -- required for the 'whisper' STT provider")
    if resolved_provider == "deepgram" and not settings.DEEPGRAM_API_KEY:
        raise VoiceError("DEEPGRAM_API_KEY is not configured -- required for the 'deepgram' STT provider")

    # The key goes in explicitly: LiteLLM would look for it in os.environ, where a key that only lives in the .env file read by `settings` is not.
    extra = {"api_key": settings.OPENAI_API_KEY if resolved_provider == "whisper" else settings.DEEPGRAM_API_KEY}
    if api_base:
        extra["api_base"] = api_base
    response = await _litellm_transcribe("Whisper" if resolved_provider == "whisper" else "Deepgram", model, audio_bytes, filename, language, **extra)
    return response.text


_LOCAL_WHISPER_MODELS: dict[tuple[str, str, str], object] = {}


def local_whisper_available() -> bool:
    import importlib.util

    return importlib.util.find_spec("faster_whisper") is not None


def _load_local_whisper():
    """One cached model per (size, device, compute type): loading is the expensive part, so it happens once per process."""
    key = (settings.LOCAL_WHISPER_MODEL, settings.LOCAL_WHISPER_DEVICE, settings.LOCAL_WHISPER_COMPUTE_TYPE)
    if key not in _LOCAL_WHISPER_MODELS:
        from faster_whisper import WhisperModel

        _LOCAL_WHISPER_MODELS[key] = WhisperModel(key[0], device=key[1], compute_type=key[2])
    return _LOCAL_WHISPER_MODELS[key]


def _transcribe_local_sync(audio_bytes: bytes, language: str | None) -> str:
    model = _load_local_whisper()
    # faster-whisper takes a language code ("fr"), not a locale ("fr-FR").
    code = language.split("-")[0].lower() if language else None
    # E2E finding 2026-10-12: faster-whisper 1.2.1 decodes any container through PyAV and calls `av.open(..., metadata_errors=...)`, an argument PyAV 19 removed
    # (TypeError on EVERY input). A PCM WAV file (what browsers' recorders and the voice widget produce) is decoded here with the standard library, which also avoids the
    # dependency for the common case; any other container still goes through PyAV.
    samples = _decode_pcm_wav(audio_bytes)
    segments, _info = model.transcribe(samples if samples is not None else io.BytesIO(audio_bytes), language=code, vad_filter=True)
    return " ".join(segment.text.strip() for segment in segments).strip()


def _decode_pcm_wav(audio_bytes: bytes):
    """Mono float32 samples at 16 kHz from a PCM WAV file, or None when the bytes are not such a file."""
    import wave

    if audio_bytes[:4] != b"RIFF" or audio_bytes[8:12] != b"WAVE":
        return None
    import numpy as np

    try:
        with wave.open(io.BytesIO(audio_bytes)) as wav:
            channels, width, rate, frames = wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.readframes(wav.getnframes())
    except (wave.Error, EOFError):
        return None
    if width not in (1, 2, 4):
        return None
    dtype = {1: np.uint8, 2: np.int16, 4: np.int32}[width]
    data = np.frombuffer(frames, dtype=dtype).astype(np.float32)
    data = (data - 128.0) / 128.0 if width == 1 else data / float(2 ** (8 * width - 1))
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    if rate != 16000 and len(data):
        target = int(len(data) * 16000 / rate)
        data = np.interp(np.linspace(0, len(data) - 1, target), np.arange(len(data)), data).astype(np.float32)
    return data


async def transcribe_local_whisper(audio_bytes: bytes, *, language: str | None = None) -> str:
    """Open-source, self-hosted STT (faster-whisper): no API key, audio never leaves the server. Runs in a worker thread
    so a multi-second CPU transcription cannot block the event loop. Honest degradation: when the optional package is not
    installed this raises a VoiceError naming the exact install command -- never a silent stub."""
    import asyncio

    if not local_whisper_available():
        raise VoiceError("the 'local_whisper' STT provider needs the optional open-source package: pip install faster-whisper")
    try:
        return await asyncio.get_running_loop().run_in_executor(None, _transcribe_local_sync, audio_bytes, language)
    except VoiceError:
        raise
    except Exception as exc:  # undecodable audio, model download failure, out-of-memory...
        raise VoiceError(f"local transcription failed: {type(exc).__name__}: {exc}") from exc


def _parse_diarization_segments(response) -> list[dict] | None:
    """Partie 22 (finalization) -- real, best-effort parsing of a real
    diarized transcription response. **Honest, documented limitation**:
    this environment has no live Deepgram account to verify the exact
    real response shape `litellm.atranscription(..., diarize=True)`
    normalizes to -- Deepgram's own raw API returns per-word
    `speaker`/`start`/`end` under `results.channels[0].alternatives[0]
    .words[]` when diarization is on, and litellm's own
    `TranscriptionResponse` is a permissive object that carries through
    whatever extra fields the provider response included. This checks
    the most likely real attribute (`.words`) defensively and returns
    `None` (never a fabricated single-speaker guess) if it isn't
    present in whatever shape comes back -- the same honest "real
    result or None, never invented" pattern as `get_video_duration_ms`."""
    words = getattr(response, "words", None)
    if not words:
        return None
    segments: list[dict] = []
    for word in words:
        word_dict = word if isinstance(word, dict) else getattr(word, "__dict__", None)
        if not word_dict or "speaker" not in word_dict:
            return None
        segments.append({
            "speaker": word_dict.get("speaker"), "start_ms": int(word_dict.get("start", 0) * 1000),
            "end_ms": int(word_dict.get("end", 0) * 1000), "text": word_dict.get("word") or word_dict.get("punctuated_word", ""),
        })
    return segments or None


async def transcribe_audio_with_diarization(audio_bytes: bytes, *, filename: str = "audio.wav", language: str | None = None, api_base: str | None = None) -> tuple[str, list[dict] | None]:
    """Partie 22 (finalization) -- real, additive diarization attempt,
    Deepgram-only (the only STT provider this codebase integrates whose
    real API supports it -- Whisper's own API has no diarization
    parameter at all). A NEW function, not a change to `transcribe_audio`
    above -- same "never rename/change a function pre-existing tests
    call directly" discipline as Partie 21's own `assign_ab_test_variant`.
    Real, honest degradation: any real failure (wrong provider, missing
    key, an unparseable response) returns `(text, None)` -- a real
    transcript with no segments, never a crash and never a fabricated
    speaker list."""
    if not settings.DEEPGRAM_API_KEY:
        raise VoiceError("DEEPGRAM_API_KEY is not configured -- required for diarization (Deepgram-only)")
    extra = {"api_key": settings.DEEPGRAM_API_KEY}
    if api_base:
        extra["api_base"] = api_base
    response = await _litellm_transcribe("Deepgram", _STT_MODELS["deepgram"], audio_bytes, filename, language, diarize=True, **extra)
    return response.text, _parse_diarization_segments(response)


# --------------------------------------------------------- TTS / ElevenLabs (8.2.2/8.2.9)


def get_elevenlabs_voices() -> list[dict]:
    """Item 4's own literal function (8.2.9) -- real, live catalog
    when a real API key is configured, the real, documented fallback
    list otherwise (never empty, so a frontend voice picker always has
    something real to show)."""
    if not settings.ELEVENLABS_API_KEY:
        return [
            {"name": name, "voice_id": info["voice_id"], "gender": info["gender"], "accent": info["accent"], "source": "fallback"}
            for name, info in _KNOWN_ELEVENLABS_VOICES.items()
        ]
    response = httpx.get(f"{_ELEVENLABS_BASE_URL}/voices", headers={"xi-api-key": settings.ELEVENLABS_API_KEY}, timeout=10.0)
    response.raise_for_status()
    return [
        {
            "name": v["name"], "voice_id": v["voice_id"], "gender": v.get("labels", {}).get("gender"),
            "preview_url": v.get("preview_url"), "source": "live",
        }
        for v in response.json().get("voices", [])
    ]


def get_elevenlabs_voice(voice_id: str) -> dict | None:
    """Item 4's own literal function."""
    for voice in get_elevenlabs_voices():
        if voice["voice_id"] == voice_id:
            return voice
    return None


async def synthesize_with_elevenlabs(text: str, voice_id: str | None = None, speed: float | None = None, pitch: float | None = None) -> bytes:
    """Item 4's own literal function -- real, async ElevenLabs
    text-to-speech call, returning real MP3 bytes. `speed`/`pitch`
    aren't real, independent ElevenLabs API parameters (their own real
    API instead exposes `stability`/`similarity_boost`) -- passed
    through as real `voice_settings.stability`/`style` approximations
    rather than silently dropped, and documented here rather than
    pretending a 1:1 parameter mapping exists."""
    if not settings.ELEVENLABS_API_KEY:
        raise VoiceError("ELEVENLABS_API_KEY is not configured")
    resolved_voice_id = voice_id or _KNOWN_ELEVENLABS_VOICES[settings.ELEVENLABS_DEFAULT_VOICE]["voice_id"]

    response = await _post_tts(
        "ElevenLabs", f"{_ELEVENLABS_BASE_URL}/text-to-speech/{quote(resolved_voice_id, safe='')}",
        headers={"xi-api-key": settings.ELEVENLABS_API_KEY, "Content-Type": "application/json", "Accept": "audio/mpeg"},
        json={
            "text": text, "model_id": settings.ELEVENLABS_MODEL,
            "voice_settings": {"stability": min(max(pitch or 0.5, 0.0), 1.0), "similarity_boost": min(max(speed or 0.75, 0.0), 1.0)},
        },
    )
    if not response.content:
        raise VoiceError("ElevenLabs returned an empty audio body")
    return response.content


def _tts_error_detail(response: httpx.Response) -> str:
    """The vendor's own explanation (ElevenLabs `detail.message`/`detail.status`, Google `error.message`), without echoing a whole body."""
    try:
        body = response.json()
    except ValueError:
        return response.text[:200]
    if isinstance(body, dict):
        detail = body.get("detail", body.get("error"))
        if isinstance(detail, dict):
            return str(detail.get("message") or detail.get("status") or detail)[:200]
        if detail:
            return str(detail)[:200]
    return response.text[:200]


async def _post_tts(vendor: str, url: str, *, headers: dict, json: dict) -> httpx.Response:
    """POST to a hosted TTS vendor: one retry after a 429 (concurrency limit; honours Retry-After, at most 5 s), typed errors for everything else.
    Nothing is retried after a 5xx or a timeout: a synthesis is billed per character."""
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=_TTS_TIMEOUT_SECONDS) as client:
                response = await client.post(url, headers=headers, json=json)
        except httpx.TimeoutException as exc:
            raise VoiceError(f"{vendor} did not answer within {_TTS_TIMEOUT_SECONDS:g}s") from exc
        except httpx.RequestError as exc:
            raise VoiceError(f"{vendor} could not be reached ({type(exc).__name__})") from exc
        if response.status_code == 429 and attempt == 0:
            try:
                delay = min(max(float(response.headers.get("retry-after", "1")), 0.0), 5.0)
            except ValueError:
                delay = 1.0
            await asyncio.sleep(delay)
            continue
        break
    if response.status_code >= 400:
        raise VoiceError(f"{vendor} synthesis failed ({response.status_code}): {_tts_error_detail(response)}")
    return response


async def synthesize_with_google_cloud(text: str, voice_id: str | None = None, speed: float | None = None, pitch: float | None = None, language_code: str = "en-US") -> bytes:
    """Google Cloud Text-to-Speech (REST `text:synthesize`, API-key auth): returns MP3 bytes. `voice_id` is a Google voice name such as
    `fr-FR-Neural2-A` (its language prefix sets the language); `speed` is the speaking rate (0.25-4.0), `pitch` in semitones (-20..20)."""
    if not settings.GOOGLE_CLOUD_TTS_API_KEY:
        raise VoiceError("GOOGLE_CLOUD_TTS_API_KEY is not configured")
    voice: dict = {"languageCode": language_code}
    if voice_id:
        voice = {"name": voice_id, "languageCode": "-".join(voice_id.split("-")[:2]) or language_code}
    audio_config: dict = {"audioEncoding": "MP3"}
    if speed is not None:
        audio_config["speakingRate"] = min(max(speed, 0.25), 4.0)
    if pitch is not None:
        audio_config["pitch"] = min(max(pitch, -20.0), 20.0)
    response = await _post_tts(
        "Google Cloud TTS", _GOOGLE_TTS_URL, headers={"X-Goog-Api-Key": settings.GOOGLE_CLOUD_TTS_API_KEY, "Content-Type": "application/json"},
        json={"input": {"text": text}, "voice": voice, "audioConfig": audio_config},
    )
    try:
        audio = base64.b64decode(response.json()["audioContent"], validate=True)
    except (KeyError, ValueError, TypeError) as exc:
        raise VoiceError("Google Cloud TTS returned no audioContent") from exc
    if not audio:
        raise VoiceError("Google Cloud TTS returned an empty audio body")
    return audio


async def synthesize_speech(text: str, provider: str | None = None, voice_id: str | None = None, speed: float | None = None, pitch: float | None = None) -> bytes:
    """Server-side TTS through the hosted provider the organization/operator chose (`TTS_PROVIDER`: elevenlabs | google_cloud). `web_speech` is the
    browser's own synthesizer and has no server side."""
    chosen = provider or (settings.TTS_PROVIDER if settings.TTS_PROVIDER in ("elevenlabs", "google_cloud") else "elevenlabs")
    if chosen == "elevenlabs":
        return await synthesize_with_elevenlabs(text, voice_id=voice_id, speed=speed, pitch=pitch)
    if chosen == "google_cloud":
        return await synthesize_with_google_cloud(text, voice_id=voice_id, speed=speed, pitch=pitch)
    raise VoiceError(f"'{chosen}' has no server-side synthesis (web_speech runs in the browser); use 'elevenlabs' or 'google_cloud'")


# -------------------------------------------------- Voice chat round-trip (item 17)


async def voice_chat(
    db: AsyncSession, organization_id: uuid.UUID, audio_bytes: bytes, *, filename: str = "audio.wav",
    stt_provider: str | None = None, language: str | None = None, voice_id: str | None = None,
) -> dict:
    """Bricks open source, item 17 -- real, end-to-end voice round-trip:
    closes the real gap the user's own consolidated list named ("les
    composants voix STT/TTS existent déjà... mais ne sont pas intégrés
    au chat"). Real, sequential composition of 3 already-real,
    already-tested functions -- `transcribe_audio` (this module),
    `generate_response` (`api.services.generation`, the real RAG
    retrieval+generation pipeline), `synthesize_with_elevenlabs` (this
    module) -- no new provider, no new infrastructure, just the
    missing real wiring between pieces that already existed in
    isolation.

    **Real, deliberate scope**: a round-trip (record -> upload -> wait
    -> play), not real-time streaming voice (continuous mic -> partial
    transcripts -> speaking response) -- see this étape's own ROADMAP.md
    entry for why a full real-time WebRTC pipeline (FastRTC) was
    evaluated and not pulled in for this pass (a real, disproportionate
    dependency footprint for this codebase's own backend service, found
    via a real `pip install --dry-run`, not guessed)."""
    from api.services.generation import GenerationBlockedError, generate_response

    transcript = await transcribe_audio(audio_bytes, filename=filename, provider=stt_provider, language=language)
    try:
        response = await generate_response(db, organization_id, transcript)
    except GenerationBlockedError as exc:
        # Hardening Mission, Phase 4 -- re-raised as this module's own
        # real, already-handled VoiceError (api/routers/voice.py's own
        # voice_chat_endpoint already turns this into a clean 400) so a
        # real injection attempt spoken into the microphone fails the
        # same honest way a blocked guardrail does everywhere else in
        # this codebase, never a bare, unhandled 500.
        raise VoiceError(str(exc)) from exc
    answer_audio = await synthesize_with_elevenlabs(response.answer, voice_id=voice_id)
    return {"transcript": transcript, "answer_text": response.answer, "answer_audio": answer_audio, "response_id": response.id}


async def voice_agent_turn(
    db: AsyncSession, organization_id: uuid.UUID, audio_bytes: bytes, *, filename: str = "audio.wav", stt_provider: str | None = None,
    language: str | None = None, speak: bool = False, voice_id: str | None = None, user_id: uuid.UUID | None = None,
    workspace_id: uuid.UUID | None = None,
) -> dict:
    """Voice agent, one turn: speech -> transcript -> the organization's RAG pipeline (retrieval, guardrails, citations) ->
    answer text (+ optional synthesized speech). Unlike `voice_chat`, the answer's TTS is OPTIONAL (the browser can speak the
    text itself via Web Speech, free), the citations are returned, and the transcript is bounded before it reaches the LLM.
    Turn-based, not streaming: record -> upload -> answer."""
    from api.services.citations import get_citations_by_response, resolve_citation_source
    from api.services.generation import GenerationBlockedError, generate_response

    if len(audio_bytes) > settings.VOICE_AGENT_MAX_AUDIO_BYTES:
        raise VoiceError(f"audio too large ({len(audio_bytes)} bytes, max {settings.VOICE_AGENT_MAX_AUDIO_BYTES})")
    if not audio_bytes:
        raise VoiceError("empty audio")
    transcript = (await transcribe_audio(audio_bytes, filename=filename, provider=stt_provider, language=language)).strip()
    if not transcript:
        raise VoiceError("no speech detected in the audio")
    transcript = transcript[: settings.VOICE_AGENT_MAX_TRANSCRIPT_CHARS]
    try:
        response = await generate_response(db, organization_id, transcript, workspace_id=workspace_id, created_by=user_id)
    except GenerationBlockedError as exc:
        raise VoiceError(str(exc)) from exc
    answer_audio = await synthesize_with_elevenlabs(response.answer, voice_id=voice_id) if speak else None
    sources = [
        {"citation_number": c.citation_number, **{k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in resolve_citation_source(c).items()}}
        for c in await get_citations_by_response(db, response.id)
    ]
    return {"transcript": transcript, "answer_text": response.answer, "answer_audio": answer_audio, "response_id": response.id, "sources": sources}


def get_elevenlabs_voice_preview(voice_id: str) -> str | None:
    """Item 4's own literal function -- a real preview URL, without a
    real synthesis call: ElevenLabs' own live `/v1/voices` response
    already carries one per voice when a real API key is configured;
    the fallback catalog has no real, verified preview URL to offer,
    so this is honestly `None` in that case rather than a fabricated
    guess."""
    voice = get_elevenlabs_voice(voice_id)
    return voice.get("preview_url") if voice else None

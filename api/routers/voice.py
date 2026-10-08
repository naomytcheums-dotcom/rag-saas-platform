"""Partie 8.2.1 (STT) + 8.2.2/8.2.9 (TTS / ElevenLabs) -- the real
server-side voice endpoints (see api/services/voice.py's own top
docstring for why the browser-only web_speech provider has no
endpoint here at all).

Bricks open source, item 17 -- `POST /voice/organizations/{org_id}/chat`
is the new, real, end-to-end voice round-trip endpoint (see
`api/services/voice.py`'s own `voice_chat` docstring). Real, documented
deviation from `api/routers/search.py`'s own `/organizations/{org_id}/...`
convention: this router already carries a real `/voice` prefix applied
to every route in it, so `org_id` can't be the very first path segment
without either duplicating "voice" in the URL or splitting this one
route into a second router -- `org_id` still resolves the real
`require_permission` check from the URL itself (this route's own real
security property), just one segment later than `search.py`'s own
convention."""

import base64
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.organization import OrganizationMember
from api.models.user import User
from api.schemas.voice import ElevenLabsVoiceResponse, SynthesizeRequest, TranscribeResponse, VoiceAgentResponse, VoiceChatResponse
from api.security.permissions import require_permission
from api.services.voice import VoiceError, get_elevenlabs_voices, synthesize_with_elevenlabs, transcribe_audio, voice_agent_turn, voice_chat

router = APIRouter(prefix="/voice", tags=["voice"])


@router.get("/elevenlabs/voices", response_model=list[ElevenLabsVoiceResponse])
async def list_elevenlabs_voices_endpoint(current_user: User = Depends(get_current_user)):
    try:
        return get_elevenlabs_voices()
    except VoiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/tts")
async def synthesize_speech_endpoint(payload: SynthesizeRequest, current_user: User = Depends(get_current_user)):
    try:
        audio = await synthesize_with_elevenlabs(payload.text, voice_id=payload.voice_id, speed=payload.speed, pitch=payload.pitch)
    except VoiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return Response(content=audio, media_type="audio/mpeg")


@router.post("/stt", response_model=TranscribeResponse)
async def transcribe_speech_endpoint(
    file: UploadFile, provider: str | None = None, language: str | None = None, current_user: User = Depends(get_current_user),
):
    audio_bytes = await file.read()
    try:
        text = await transcribe_audio(audio_bytes, filename=file.filename or "audio.wav", provider=provider, language=language)
    except VoiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return TranscribeResponse(text=text)


@router.post("/organizations/{org_id}/chat", response_model=VoiceChatResponse)
async def voice_chat_endpoint(
    org_id: uuid.UUID, file: UploadFile, stt_provider: str | None = None, language: str | None = None, voice_id: str | None = None,
    _caller: OrganizationMember = Depends(require_permission("documents:write")), db: AsyncSession = Depends(get_db),
):
    audio_bytes = await file.read()
    try:
        result = await voice_chat(
            db, org_id, audio_bytes, filename=file.filename or "audio.wav",
            stt_provider=stt_provider, language=language, voice_id=voice_id,
        )
    except VoiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    return VoiceChatResponse(
        transcript=result["transcript"], answer_text=result["answer_text"],
        answer_audio_base64=base64.b64encode(result["answer_audio"]).decode("ascii"),
        response_id=result["response_id"],
    )


@router.post("/organizations/{org_id}/agent", response_model=VoiceAgentResponse)
async def voice_agent_endpoint(
    org_id: uuid.UUID, file: UploadFile, stt_provider: str | None = None, language: str | None = None, speak: bool = False, voice_id: str | None = None,
    caller: OrganizationMember = Depends(require_permission("documents:read")), db: AsyncSession = Depends(get_db),
):
    """Voice agent turn: audio in -> speech-to-text (open-source `local_whisper` or a hosted provider) -> the organization's RAG
    pipeline -> answer + sources (+ synthesized speech when `speak=true`). Same guards as every other paid entry point: rate limit
    per organization, balance + daily/monthly spend caps pre-flight (BYOK exempt), bounded audio and transcript, a flat per-turn
    credit charge for non-BYOK organizations, injection guardrails (a blocked utterance answers 400)."""
    from api.config import settings
    from api.security.rate_limit import enforce_rate_limit
    from api.services.billing_credits import InsufficientCreditsError, SpendCapExceededError, assert_org_can_spend, deduct_credits
    from api.services.llm_config import resolve_llm_config
    from api.security.organization_settings import get_org_settings
    from api.services.llm_byok import resolve_org_api_key

    await enforce_rate_limit(f"ratelimit:voice_agent:org:{org_id}", settings.VOICE_AGENT_RATE_LIMIT_MAX_ATTEMPTS, settings.VOICE_AGENT_RATE_LIMIT_WINDOW_SECONDS)
    org_settings = await get_org_settings(db, org_id)
    provider = resolve_llm_config(org_settings)["provider"]
    try:
        await assert_org_can_spend(db, org_id, org_settings, provider)
    except InsufficientCreditsError as exc:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Insufficient AI credits -- add a credit pack or configure your own provider key (BYOK)") from exc
    except SpendCapExceededError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"Spend cap exceeded: {exc}") from exc

    audio_bytes = await file.read(settings.VOICE_AGENT_MAX_AUDIO_BYTES + 1)
    try:
        result = await voice_agent_turn(
            db, org_id, audio_bytes, filename=file.filename or "audio.wav", stt_provider=stt_provider, language=language,
            speak=speak, voice_id=voice_id, user_id=caller.user_id,
        )
    except VoiceError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    charged = 0
    if not await resolve_org_api_key(db, org_id, provider):
        try:
            await deduct_credits(db, org_id, settings.VOICE_AGENT_TURN_CREDIT_COST, resource_type="voice_agent_turn")
            charged = settings.VOICE_AGENT_TURN_CREDIT_COST
        except InsufficientCreditsError:
            pass  # the answer was already produced; the pre-flight above is the gate, a race only costs one turn
    await db.commit()
    audio = result["answer_audio"]
    return VoiceAgentResponse(
        transcript=result["transcript"], answer_text=result["answer_text"],
        answer_audio_base64=base64.b64encode(audio).decode("ascii") if audio else None,
        response_id=result["response_id"], sources=result["sources"], credits_charged=charged,
    )

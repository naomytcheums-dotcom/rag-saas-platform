"""Partie 8.2.1 (STT) + 8.2.2/8.2.9 (TTS / ElevenLabs) -- the real
server-side voice endpoints (see api/services/voice.py's own top
docstring for why the browser-only web_speech provider has no
endpoint here at all)."""

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status

from api.dependencies import get_current_user
from api.models.user import User
from api.schemas.voice import ElevenLabsVoiceResponse, SynthesizeRequest, TranscribeResponse
from api.services.voice import VoiceError, get_elevenlabs_voices, synthesize_with_elevenlabs, transcribe_audio

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

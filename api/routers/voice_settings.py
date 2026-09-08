"""Partie 8.2.8 -- Voice settings."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from api.models.user import User
from api.schemas.voice_settings import VoiceSettingsResponse, VoiceSettingsUpdateRequest
from api.services.voice_settings import VoiceSettingsError, get_voice_settings, reset_voice_settings, update_voice_settings

router = APIRouter(prefix="/users/me/voice-settings", tags=["voice-settings"])


@router.get("", response_model=VoiceSettingsResponse)
async def get_voice_settings_endpoint(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    settings_row = await get_voice_settings(db, current_user.id)
    await db.commit()
    return settings_row


@router.patch("", response_model=VoiceSettingsResponse)
async def update_voice_settings_endpoint(
    payload: VoiceSettingsUpdateRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    try:
        settings_row = await update_voice_settings(db, current_user.id, payload.model_dump(exclude_unset=True))
    except VoiceSettingsError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(settings_row)
    return settings_row


@router.post("/reset", response_model=VoiceSettingsResponse)
async def reset_voice_settings_endpoint(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    settings_row = await reset_voice_settings(db, current_user.id)
    await db.commit()
    await db.refresh(settings_row)
    return settings_row

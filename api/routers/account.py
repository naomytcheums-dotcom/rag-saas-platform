"""
1.1.10 soft-delete, 1.1.11 RGPD export, 1.1.13 profile/avatar,
1.1.14 preferences. 1.1.12 (RGPD consent) has no dedicated endpoint --
consent_given_at/terms_version are captured once at registration
(api/routers/auth.py) and surfaced read-only via GET /account/me.
"""

import datetime as dt
import json

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.dependencies import get_current_user, get_db
from api.models.oauth import OAuthAccount
from api.models.session import Session
from api.models.user import User
from api.schemas.auth import MessageResponse
from api.schemas.user import PreferencesUpdateRequest, ProfileUpdateRequest, UserProfileResponse
from api.services.storage import upload_avatar

router = APIRouter(prefix="/account", tags=["account"])


@router.get("/me", response_model=UserProfileResponse)
async def get_profile(current_user: User = Depends(get_current_user)):
    return UserProfileResponse.model_validate(current_user)


@router.patch("/profile", response_model=UserProfileResponse)
async def update_profile(payload: ProfileUpdateRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if payload.full_name is not None:
        current_user.full_name = payload.full_name
    if payload.company is not None:
        current_user.company = payload.company
    await db.commit()
    await db.refresh(current_user)
    return UserProfileResponse.model_validate(current_user)


@router.patch("/preferences", response_model=UserProfileResponse)
async def update_preferences(payload: PreferencesUpdateRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if payload.locale is not None:
        current_user.locale = payload.locale
    if payload.timezone is not None:
        current_user.timezone = payload.timezone
    await db.commit()
    await db.refresh(current_user)
    return UserProfileResponse.model_validate(current_user)


@router.post("/avatar", response_model=UserProfileResponse)
async def upload_avatar_route(file: UploadFile, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    content = await file.read()
    try:
        url = upload_avatar(current_user.id, content, file.content_type or "application/octet-stream")
    except (ValueError, EnvironmentError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    current_user.avatar_url = url
    await db.commit()
    await db.refresh(current_user)
    return UserProfileResponse.model_validate(current_user)


@router.delete("/me", response_model=MessageResponse)
async def delete_account(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    now = dt.datetime.now(dt.timezone.utc)
    current_user.is_active = False
    current_user.deleted_at = now
    current_user.deletion_scheduled_at = now + dt.timedelta(days=settings.ACCOUNT_PURGE_DELAY_DAYS)

    # Log every device out immediately -- the account is deactivated now,
    # the hard purge (api/tasks/account_purge.py) just happens later.
    await db.execute(delete(Session).where(Session.user_id == current_user.id))
    await db.commit()

    return MessageResponse(
        message=f"Account deactivated. It will be permanently deleted in {settings.ACCOUNT_PURGE_DELAY_DAYS} days."
    )


@router.get("/export")
async def export_account_data(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    oauth_accounts = await db.scalars(select(OAuthAccount).where(OAuthAccount.user_id == current_user.id))
    sessions = await db.scalars(select(Session).where(Session.user_id == current_user.id))

    export = {
        "profile": {
            "id": str(current_user.id),
            "email": current_user.email,
            "full_name": current_user.full_name,
            "company": current_user.company,
            "locale": current_user.locale,
            "timezone": current_user.timezone,
            "is_email_verified": current_user.is_email_verified,
            "two_factor_enabled": current_user.totp_enabled,
            "created_at": current_user.created_at.isoformat(),
        },
        "consent": {
            "consent_given_at": current_user.consent_given_at.isoformat() if current_user.consent_given_at else None,
            "terms_version": current_user.terms_version,
        },
        # Linked provider + verified email only -- never provider access
        # tokens, which this app doesn't even persist (see oauth.py).
        "linked_oauth_accounts": [
            {"provider": a.provider.value, "provider_email": a.provider_email, "linked_at": a.created_at.isoformat()}
            for a in oauth_accounts
        ],
        # Device/IP/timestamps only -- never the refresh token hash itself.
        "sessions": [
            {
                "device_info": s.device_info,
                "ip_address": s.ip_address,
                "created_at": s.created_at.isoformat(),
                "last_seen_at": s.last_seen_at.isoformat(),
                "revoked": s.revoked_at is not None,
            }
            for s in sessions
        ],
        "exported_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }

    return Response(
        content=json.dumps(export, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=account-data-export.json"},
    )

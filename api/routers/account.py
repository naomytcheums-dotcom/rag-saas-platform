"""
1.1.10 soft-delete, 1.1.11 RGPD export, 1.1.12 consent withdrawal,
1.1.13 profile/avatar, 1.1.14 preferences. consent_given_at/terms_version
are captured once at registration (api/routers/auth.py) and surfaced
read-only via GET /account/me; withdrawing that consent is the one part
of 1.1.12 that needs its own endpoint, see withdraw_consent() below.
"""

import datetime as dt
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.dependencies import get_current_user, get_db
from api.models.oauth import OAuthAccount
from api.models.restore_token import AccountRestoreToken
from api.models.session import Session
from api.models.user import User
from api.schemas.auth import AccountRestoreConfirmRequest, AccountRestoreRequest, MessageResponse
from api.schemas.user import PreferencesUpdateRequest, ProfileUpdateRequest, UserProfileResponse
from api.security.hashing import hash_token
from api.security.rate_limit import enforce_rate_limit
from api.services.account_restore import create_and_send_account_restore
from api.services.email import send_consent_withdrawn_email
from api.services.storage import upload_avatar
from api.utils import as_aware_utc

router = APIRouter(prefix="/account", tags=["account"])
logger = logging.getLogger(__name__)

_GENERIC_RESTORE_MESSAGE = "If a deactivated account exists for that email and its grace period hasn't ended, a restore link has been sent."


@router.get("/me", response_model=UserProfileResponse)
async def get_profile(current_user: User = Depends(get_current_user)):
    """The logged-in user's own profile -- whoever the access token
    belongs to, resolved by the get_current_user dependency."""
    return UserProfileResponse.model_validate(current_user)


@router.patch("/profile", response_model=UserProfileResponse)
async def update_profile(payload: ProfileUpdateRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Partial update: only the fields actually present in the request body
    get changed (payload.full_name is None means "leave it alone", not
    "clear it") -- so a frontend can PATCH just the one field the user
    edited without having to resend the whole profile.
    """
    if payload.full_name is not None:
        current_user.full_name = payload.full_name
    if payload.company is not None:
        current_user.company = payload.company
    await db.commit()
    await db.refresh(current_user)
    return UserProfileResponse.model_validate(current_user)


@router.patch("/preferences", response_model=UserProfileResponse)
async def update_preferences(payload: PreferencesUpdateRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Same partial-update pattern as update_profile above, for locale
    (UI language) and timezone (validated against the real IANA
    timezone list in api/schemas/user.py -- garbage in is rejected
    before it ever reaches here, not silently stored)."""
    if payload.locale is not None:
        current_user.locale = payload.locale
    if payload.timezone is not None:
        current_user.timezone = payload.timezone
    await db.commit()
    await db.refresh(current_user)
    return UserProfileResponse.model_validate(current_user)


@router.post("/avatar", response_model=UserProfileResponse)
async def upload_avatar_route(file: UploadFile, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Uploads a new avatar image and replaces the user's avatar_url with
    it. All the actual validation (allowed image types, size limit) and
    the S3/R2/Supabase Storage call itself live in
    api/services/storage.py -- this route is just the HTTP plumbing
    around it: read the uploaded bytes, call the service, translate its
    exceptions into the right HTTP status codes, save the resulting URL.
    """
    content = await file.read()
    try:
        url = upload_avatar(current_user.id, content)
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
    """
    Soft-delete (1.1.10): the account is deactivated and every session
    revoked *immediately*, but the row itself sticks around for
    ACCOUNT_PURGE_DELAY_DAYS (a grace window, in case the user changes
    their mind or it was a mistake). The actual permanent deletion is a
    separate, scheduled step -- see api/tasks/account_purge.py -- not
    something this endpoint does itself.
    """
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


@router.post("/restore/request", response_model=MessageResponse)
async def request_account_restore(payload: AccountRestoreRequest, db: AsyncSession = Depends(get_db)):
    """
    Step 1 of undoing a self-service DELETE /account/me before the grace
    period's automatic purge (api/tasks/account_purge.py) runs. Public,
    not behind get_current_user: the account is deactivated, so there is
    no access token to authenticate with. Always returns the same generic
    message regardless of whether the email belongs to a real,
    still-restorable account -- same anti-enumeration reasoning as
    POST /auth/password/forgot.

    Rate-limited by email, same reasoning as /auth/password/forgot: stop
    someone from spamming a specific victim's inbox with restore emails.
    """
    await enforce_rate_limit(
        f"ratelimit:restore:email:{payload.email}",
        settings.ACCOUNT_RESTORE_RATE_LIMIT_MAX_ATTEMPTS, settings.ACCOUNT_RESTORE_RATE_LIMIT_WINDOW_SECONDS,
    )

    user = await db.scalar(select(User).where(User.email == payload.email))
    now = dt.datetime.now(dt.timezone.utc)
    if (
        user is not None
        and user.is_deleted
        and user.deletion_scheduled_at is not None
        and as_aware_utc(user.deletion_scheduled_at) > now
    ):
        await create_and_send_account_restore(db, user)
        await db.commit()
    return MessageResponse(message=_GENERIC_RESTORE_MESSAGE)


@router.post("/restore/confirm", response_model=MessageResponse)
async def confirm_account_restore(payload: AccountRestoreConfirmRequest, db: AsyncSession = Depends(get_db)):
    """
    Step 2: the user clicked the link from their email. Reactivates the
    account (clears deleted_at/deletion_scheduled_at, so
    account_purge.py's query -- which only selects rows where
    deletion_scheduled_at is set and due -- will no longer touch this
    row) but deliberately does NOT log them in directly, same reasoning
    as POST /auth/password/reset not doing so: this token proves control
    of the mailbox, not the password, so the user still authenticates
    through the real login flow afterward (which also correctly
    re-applies 2FA if it was enabled on the account).
    """
    invalid = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired restore link")

    restore_row = await db.scalar(select(AccountRestoreToken).where(AccountRestoreToken.token_hash == hash_token(payload.token)))
    now = dt.datetime.now(dt.timezone.utc)
    if restore_row is None or restore_row.used_at is not None or as_aware_utc(restore_row.expires_at) < now:
        raise invalid

    user = await db.get(User, restore_row.user_id)
    if user is None or not user.is_deleted:
        raise invalid

    user.is_active = True
    user.deleted_at = None
    user.deletion_scheduled_at = None
    restore_row.used_at = now

    await db.commit()
    return MessageResponse(message="Account restored. Please log in.")


@router.post("/consent/withdraw", response_model=MessageResponse)
async def withdraw_consent(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    RGPD Art. 7(3): withdrawing consent must be as easy as giving it, and
    Art. 21 gives a separate right to object to processing without also
    demanding erasure -- so unlike DELETE /account/me below, this does
    NOT schedule a purge. The account is still deactivated and every
    session revoked immediately, since continuing to serve a logged-in
    account is itself "processing" that withdrawn consent no longer
    covers; the data itself is simply kept, not erased, until the user
    separately asks for that (DELETE /account/me).
    """
    if current_user.consent_withdrawn_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Consent has already been withdrawn")

    current_user.consent_withdrawn_at = dt.datetime.now(dt.timezone.utc)
    current_user.is_active = False
    await db.execute(delete(Session).where(Session.user_id == current_user.id))
    await db.commit()

    try:
        send_consent_withdrawn_email(current_user.email)
    except (EnvironmentError, RuntimeError) as exc:
        logger.warning("failed to send consent-withdrawal confirmation to %s: %s", current_user.email, exc)

    return MessageResponse(message="Consent withdrawn. Your account has been deactivated.")


@router.get("/export")
async def export_account_data(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    RGPD/GDPR data export (1.1.11): everything this app knows about the
    requesting user, as a single downloadable JSON file (the
    Content-Disposition header below makes a browser save it as a file
    instead of just displaying the JSON inline). Only ever the caller's
    own data -- current_user comes from their own access token, there's
    no user_id parameter an attacker could swap in to read someone
    else's export. Deliberately excludes anything that isn't the user's
    own data to know about: no password hash, no refresh-token hashes,
    no other users' OAuth access tokens (which this app doesn't even
    store -- see oauth.py's docstring).
    """
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
            # consent_withdrawn_at is deliberately not included here: it's
            # only ever set together with is_active=False (see
            # withdraw_consent() above), and get_current_user's is_active
            # gate means no request could ever reach this endpoint with
            # that field set to anything but None -- it would be a
            # permanently-dead key in every export this code path can
            # actually produce.
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

"""
1.1.10 soft-delete, 1.1.11 RGPD export, 1.1.12 consent withdrawal,
1.1.13 profile/avatar, 1.1.14 preferences. consent_given_at/terms_version
are captured once at registration (api/routers/auth.py) and surfaced
read-only via GET /account/me; withdrawing that consent is the one part
of 1.1.12 that needs its own endpoint, see withdraw_consent() below.

Routes that use get_current_user_any_consent_status instead of
get_current_user (see api/dependencies.py) are the deliberate exceptions
to 4.3's "accept updated terms before doing anything else" gate: the
RGPD rights themselves (export, delete, withdraw consent), basic session
security (list/revoke sessions), reading your own profile, and the
accept-updated-terms endpoint that fixes the gate in the first place.
"""

import asyncio
import datetime as dt
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.dependencies import get_current_user, get_current_user_any_consent_status, get_db
from api.models.audit_log import AuditAction
from api.models.consent_reactivation_token import ConsentReactivationToken
from api.models.restore_token import AccountRestoreToken
from api.models.user import User
from api.schemas.auth import (
    AcceptUpdatedTermsRequest,
    AccountRestoreConfirmRequest,
    AccountRestoreRequest,
    ChangePasswordRequest,
    ConsentReactivationConfirmRequest,
    ConsentReactivationRequest,
    MessageResponse,
    SetPasswordRequest,
)
from api.schemas.user import PreferencesUpdateRequest, ProfileUpdateRequest, UserProfileResponse
from api.security.audit_log import log_audit_action
from api.security.hashing import hash_password, hash_token, verify_password
from api.security.password_history import reject_if_password_reused, record_password_change
from api.security.password_similarity import is_password_too_similar
from api.security.password_strength import is_password_known_breached
from api.security.rate_limit import enforce_rate_limit
from api.security.sessions import revoke_all_sessions_for_user
from api.services.account_restore import create_and_send_account_restore
from api.services.consent_reactivation import create_and_send_consent_reactivation
from api.services.data_export import build_account_export_data, render_account_export_csv
from api.services.email import (
    send_account_deletion_scheduled_email,
    send_consent_withdrawn_email,
    send_password_changed_email,
    send_password_set_email,
    send_preferences_changed_email,
    send_profile_changed_email,
)
from api.utils import client_ip
from api.services.storage import upload_avatar
from api.utils import as_aware_utc

router = APIRouter(prefix="/account", tags=["account"])
logger = logging.getLogger(__name__)

_GENERIC_RESTORE_MESSAGE = "If a deactivated account exists for that email and its grace period hasn't ended, a restore link has been sent."
_GENERIC_CONSENT_REACTIVATION_MESSAGE = "If a consent-withdrawn account exists for that email, a reactivation link has been sent."


@router.get("/me", response_model=UserProfileResponse)
async def get_profile(current_user: User = Depends(get_current_user_any_consent_status)):
    """The logged-in user's own profile -- whoever the access token
    belongs to, resolved by the get_current_user_any_consent_status
    dependency (not get_current_user: a frontend must be able to read
    this even for an account stuck behind 4.3's stale-terms gate, or it
    has nothing to show the "please accept updated terms" prompt with)."""
    return UserProfileResponse.model_validate(current_user)


@router.post("/consent/accept-updated-terms", response_model=MessageResponse)
async def accept_updated_terms(
    payload: AcceptUpdatedTermsRequest, current_user: User = Depends(get_current_user_any_consent_status), db: AsyncSession = Depends(get_db),
):
    """
    4.3: the fix for get_current_user's stale-terms gate. Uses
    get_current_user_any_consent_status, not get_current_user -- this
    endpoint's entire purpose is to be reachable precisely when the
    normal dependency would refuse the request, so it obviously can't
    depend on the problem already being solved.

    accept_terms must be True (schema-validated): re-consent has to be a
    freely given, affirmative act, not a default assumed by merely
    calling this endpoint.
    """
    current_user.terms_version = settings.TERMS_VERSION
    current_user.consent_given_at = dt.datetime.now(dt.timezone.utc)
    await db.commit()
    return MessageResponse(message="Thank you -- you've accepted the current terms of service.")


@router.patch("/profile", response_model=UserProfileResponse)
async def update_profile(payload: ProfileUpdateRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Partial update: only the fields actually present in the request body
    get changed (payload.full_name is None means "leave it alone", not
    "clear it") -- so a frontend can PATCH just the one field the user
    edited without having to resend the whole profile.

    Audit finding 24: emails the account once a PATCH actually changes
    something (RGPD Art. 12/13 transparency -- the data subject should
    know when their own stored data changes) -- never for a no-op PATCH
    with no recognized fields present, which would otherwise send a
    "your profile was updated" email describing no actual update.
    """
    changed_fields = []
    if payload.full_name is not None:
        current_user.full_name = payload.full_name
        changed_fields.append("full_name")
    if payload.company is not None:
        current_user.company = payload.company
        changed_fields.append("company")
    await db.commit()
    await db.refresh(current_user)

    if changed_fields:
        try:
            await asyncio.to_thread(send_profile_changed_email, current_user.email, changed_fields)
        except (EnvironmentError, RuntimeError) as exc:
            logger.warning("failed to send profile-changed notification to %s: %s", current_user.email, exc)

    return UserProfileResponse.model_validate(current_user)


@router.patch("/preferences", response_model=UserProfileResponse)
async def update_preferences(payload: PreferencesUpdateRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Same partial-update pattern as update_profile above, for locale
    (UI language) and timezone (validated against the real IANA
    timezone list in api/schemas/user.py -- garbage in is rejected
    before it ever reaches here, not silently stored).

    Audit finding 25: same "email only on an actual change" notification
    as update_profile above, see that endpoint's docstring for why.
    """
    changed_fields = []
    if payload.locale is not None:
        current_user.locale = payload.locale
        changed_fields.append("locale")
    if payload.timezone is not None:
        current_user.timezone = payload.timezone
        changed_fields.append("timezone")
    await db.commit()
    await db.refresh(current_user)

    if changed_fields:
        try:
            await asyncio.to_thread(send_preferences_changed_email, current_user.email, changed_fields)
        except (EnvironmentError, RuntimeError) as exc:
            logger.warning("failed to send preferences-changed notification to %s: %s", current_user.email, exc)

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


@router.post("/set-password", response_model=MessageResponse)
async def set_password(payload: SetPasswordRequest, request: Request, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Lets an OAuth-only account (hashed_password is None -- see
    api/models/user.py's docstring) add a password as a backup login
    method. Without this, a user who only ever signed in via Google/
    GitHub has no fallback at all if they lose access to that provider
    account (it's disabled, they're locked out of it, the provider has
    an outage) -- this app would have no way for them to prove who they
    are, ever again.

    Requires only a valid access token, not the current password --
    there IS no current password for this account, that's the whole
    reason this endpoint exists. Already-authenticated is the bar every
    other profile change in this router uses too (update_profile,
    update_preferences, upload_avatar_route); a fresh confirmation email
    is what covers the fact that this specific change adds a whole new
    way to authenticate into the account.
    """
    if current_user.hashed_password is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account already has a password -- use POST /account/change-password to change it",
        )

    if await is_password_known_breached(payload.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password has appeared in a known data breach -- please choose a different one.",
        )

    if is_password_too_similar(payload.new_password, current_user.email, current_user.full_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password is too similar to your email or name -- please choose a more distinct one.",
        )

    # No reuse check against hashed_password itself (it's None -- there
    # is no current password), but still checked against PasswordHistory:
    # an account can reach this endpoint after previously having HAD a
    # password (set here, then somehow cleared -- not a flow this app
    # exposes today, but the check costs one query either way and closes
    # the gap if that ever changes).
    await reject_if_password_reused(db, current_user.id, payload.new_password, None)

    new_hashed_password = hash_password(payload.new_password)
    current_user.hashed_password = new_hashed_password
    await record_password_change(db, current_user.id, new_hashed_password)
    await log_audit_action(
        db, user_id=current_user.id, action=AuditAction.PASSWORD_SET, ip=client_ip(request),
        user_agent=request.headers.get("user-agent"), success=True,
    )
    await db.commit()

    try:
        await asyncio.to_thread(send_password_set_email, current_user.email)
    except (EnvironmentError, RuntimeError) as exc:
        logger.warning("failed to send password-set confirmation to %s: %s", current_user.email, exc)

    return MessageResponse(message="Password set. You can now also log in with your email and password.")


@router.post("/change-password", response_model=MessageResponse)
async def change_password(payload: ChangePasswordRequest, request: Request, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    1.1-audit finding: before this endpoint existed, a logged-in user who
    knew their current password had no way to change it without going
    through the email-based forgot/reset flow -- a real completeness gap
    and an unnecessary friction point (and an unnecessary email round-trip)
    for the single most common reason to change a password at all:
    routine rotation by someone who isn't locked out.

    Requires the CURRENT password, not just a valid access token -- same
    reasoning as every other endpoint here that lets a stolen-but-still-
    valid access token do something the token alone shouldn't be enough
    for (api/routers/two_factor.py's /disable, /recovery-codes/regenerate).
    Refuses outright for an OAuth-only account (hashed_password is None)
    -- there's no current password to confirm, POST /account/set-password
    is the correct endpoint for that case.

    Revokes every session (this one included) exactly like
    POST /auth/password/reset does: a password change is exactly as
    security-sensitive as a reset, whether the user arrived at it by
    email link or from an authenticated settings page. The caller's own
    access token is blacklisted by this same call, so the response is the
    last thing this session can do -- a fresh login is required
    afterward, on this device too.
    """
    if current_user.hashed_password is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account has no password yet -- use POST /account/set-password instead",
        )
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    if await is_password_known_breached(payload.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password has appeared in a known data breach -- please choose a different one.",
        )

    if is_password_too_similar(payload.new_password, current_user.email, current_user.full_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password is too similar to your email or name -- please choose a more distinct one.",
        )

    await reject_if_password_reused(db, current_user.id, payload.new_password, current_user.hashed_password)

    new_hashed_password = hash_password(payload.new_password)
    current_user.hashed_password = new_hashed_password
    await record_password_change(db, current_user.id, new_hashed_password)
    await revoke_all_sessions_for_user(db, current_user.id)
    await log_audit_action(
        db, user_id=current_user.id, action=AuditAction.PASSWORD_CHANGED, ip=client_ip(request),
        user_agent=request.headers.get("user-agent"), success=True,
    )
    await db.commit()

    try:
        await asyncio.to_thread(send_password_changed_email, current_user.email)
    except (EnvironmentError, RuntimeError) as exc:
        logger.warning("failed to send password-changed confirmation to %s: %s", current_user.email, exc)

    return MessageResponse(message="Password changed. Please log in again.")


@router.delete("/me", response_model=MessageResponse)
async def delete_account(request: Request, current_user: User = Depends(get_current_user_any_consent_status), db: AsyncSession = Depends(get_db)):
    """
    Soft-delete (1.1.10): the account is deactivated and every session
    revoked *immediately*, but the row itself sticks around for
    ACCOUNT_PURGE_DELAY_DAYS (a grace window, in case the user changes
    their mind or it was a mistake). The actual permanent deletion is a
    separate, scheduled step -- see api/tasks/account_purge.py -- not
    something this endpoint does itself.

    Uses get_current_user_any_consent_status, not get_current_user
    (4.3): the right to erasure (RGPD Art. 17) can't be conditioned on
    first accepting terms the user is trying to leave over.
    """
    now = dt.datetime.now(dt.timezone.utc)
    current_user.is_active = False
    current_user.deleted_at = now
    current_user.deletion_scheduled_at = now + dt.timedelta(days=settings.ACCOUNT_PURGE_DELAY_DAYS)
    # A fresh deletion cycle -- if this account was previously deleted,
    # restored, and is now being deleted again, the pre-purge reminder
    # (api/tasks/account_deletion_reminder.py) must be eligible to fire
    # again too, not permanently silenced by the earlier cycle.
    current_user.deletion_reminder_sent_at = None

    # Log every device out immediately -- the account is deactivated now,
    # the hard purge (api/tasks/account_purge.py) just happens later.
    # 1.1.15: blacklists each session's access token too, not just its
    # refresh token.
    await revoke_all_sessions_for_user(db, current_user.id)
    await log_audit_action(
        db, user_id=current_user.id, action=AuditAction.ACCOUNT_DELETED, ip=client_ip(request),
        user_agent=request.headers.get("user-agent"), success=True,
    )
    await db.commit()

    try:
        await asyncio.to_thread(send_account_deletion_scheduled_email, current_user.email, current_user.deletion_scheduled_at.isoformat())
    except (EnvironmentError, RuntimeError) as exc:
        logger.warning("failed to send deletion-scheduled confirmation to %s: %s", current_user.email, exc)

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
    # 4.6: so a LATER deletion cycle's pre-purge reminder
    # (api/tasks/account_deletion_reminder.py) is eligible to fire again,
    # not permanently silenced by this now-cancelled one.
    user.deletion_reminder_sent_at = None
    restore_row.used_at = now

    await db.commit()
    return MessageResponse(message="Account restored. Please log in.")


@router.post("/consent/withdraw", response_model=MessageResponse)
async def withdraw_consent(request: Request, current_user: User = Depends(get_current_user_any_consent_status), db: AsyncSession = Depends(get_db)):
    """
    RGPD Art. 7(3): withdrawing consent must be as easy as giving it, and
    Art. 21 gives a separate right to object to processing without also
    demanding erasure -- so unlike DELETE /account/me below, this does
    NOT schedule a purge. The account is still deactivated and every
    session revoked immediately, since continuing to serve a logged-in
    account is itself "processing" that withdrawn consent no longer
    covers; the data itself is simply kept, not erased, until the user
    separately asks for that (DELETE /account/me).

    Uses get_current_user_any_consent_status, not get_current_user
    (4.3): withdrawing consent, or objecting to processing, cannot
    itself be gated behind first consenting to something new.
    """
    if current_user.consent_withdrawn_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Consent has already been withdrawn")

    current_user.consent_withdrawn_at = dt.datetime.now(dt.timezone.utc)
    current_user.is_active = False
    # 1.1.15: blacklists each session's access token too, not just its
    # refresh token.
    await revoke_all_sessions_for_user(db, current_user.id)
    await log_audit_action(
        db, user_id=current_user.id, action=AuditAction.CONSENT_WITHDRAWN, ip=client_ip(request),
        user_agent=request.headers.get("user-agent"), success=True,
    )
    await db.commit()

    try:
        await asyncio.to_thread(send_consent_withdrawn_email, current_user.email)
    except (EnvironmentError, RuntimeError) as exc:
        logger.warning("failed to send consent-withdrawal confirmation to %s: %s", current_user.email, exc)

    return MessageResponse(message="Consent withdrawn. Your account has been deactivated.")


@router.post("/consent/reactivate/request", response_model=MessageResponse)
async def request_consent_reactivation(payload: ConsentReactivationRequest, db: AsyncSession = Depends(get_db)):
    """
    Step 1 of undoing POST /account/consent/withdraw -- withdrawing
    consent must not be a silent one-way door (contrast with a full
    DELETE /account/me, which already has its own /restore/* pair below;
    this is that same idea applied to the consent-withdrawal path).
    Public, not behind get_current_user: the account is deactivated, so
    there's no access token to authenticate with. Always returns the
    same generic message regardless of whether the email belongs to a
    real, consent-withdrawn account -- same anti-enumeration reasoning as
    POST /auth/password/forgot and /account/restore/request.

    Deliberately does NOT fire for an account that's also soft-deleted
    (is_deleted) -- that account needs /account/restore/*, a full
    DELETE is a stronger, separate state that a mere consent reactivation
    must not silently undo.
    """
    await enforce_rate_limit(
        f"ratelimit:consent-reactivate:email:{payload.email}",
        settings.ACCOUNT_RESTORE_RATE_LIMIT_MAX_ATTEMPTS, settings.ACCOUNT_RESTORE_RATE_LIMIT_WINDOW_SECONDS,
    )

    user = await db.scalar(select(User).where(User.email == payload.email))
    if user is not None and user.consent_withdrawn_at is not None and not user.is_deleted:
        await create_and_send_consent_reactivation(db, user)
        await db.commit()
    return MessageResponse(message=_GENERIC_CONSENT_REACTIVATION_MESSAGE)


@router.post("/consent/reactivate/confirm", response_model=MessageResponse)
async def confirm_consent_reactivation(payload: ConsentReactivationConfirmRequest, db: AsyncSession = Depends(get_db)):
    """
    Step 2: the user clicked the link from their email and accepted the
    current terms again -- accept_terms is validated True by the schema,
    since consent has to be freely given again, not silently restored to
    whatever it was before withdrawal. Reactivates the account
    (is_active=True, consent_withdrawn_at cleared) but, same reasoning as
    /account/restore/confirm and /auth/password/reset, does NOT log the
    user in directly: this token proves control of the mailbox, not the
    password, so they still authenticate through the real login flow
    afterward.
    """
    invalid = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reactivation link")

    row = await db.scalar(select(ConsentReactivationToken).where(ConsentReactivationToken.token_hash == hash_token(payload.token)))
    now = dt.datetime.now(dt.timezone.utc)
    if row is None or row.used_at is not None or as_aware_utc(row.expires_at) < now:
        raise invalid

    user = await db.get(User, row.user_id)
    if user is None or user.consent_withdrawn_at is None or user.is_deleted:
        raise invalid

    user.is_active = True
    user.consent_withdrawn_at = None
    # A fresh consent record, not the old one resurrected -- this moment
    # is when they actually agreed again, same reasoning as register()'s
    # consent_given_at capturing the real moment of agreement.
    user.consent_given_at = now
    user.terms_version = settings.TERMS_VERSION
    row.used_at = now

    await db.commit()
    return MessageResponse(message="Your account has been reactivated. Please log in.")


@router.get("/export")
async def export_account_data(current_user: User = Depends(get_current_user_any_consent_status), db: AsyncSession = Depends(get_db)):
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

    Uses get_current_user_any_consent_status, not get_current_user
    (4.3): the right to access/portability (RGPD Art. 15/20) can't be
    conditioned on accepting new terms first.

    consent_withdrawn_at is deliberately not included in the export: it's
    only ever set together with is_active=False (see withdraw_consent()
    above), and get_current_user_any_consent_status's is_active gate
    means no request could ever reach this endpoint with that field set
    to anything but None -- it would be a permanently-dead key in every
    export this code path can actually produce.
    """
    export = await build_account_export_data(db, current_user)

    return Response(
        content=json.dumps(export, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=account-data-export.json"},
    )


@router.get("/export-csv")
async def export_account_data_csv(current_user: User = Depends(get_current_user_any_consent_status), db: AsyncSession = Depends(get_db)):
    """
    Audit finding 23: the same data as GET /account/export above, as CSV
    instead of JSON -- RGPD Art. 20's "structured, commonly used,
    machine-readable format" doesn't mandate JSON specifically, and a
    non-technical user is far more likely to be able to open a CSV in a
    spreadsheet than to make sense of nested JSON. Shares
    build_account_export_data with the JSON endpoint (api/services/
    data_export.py) so the two formats can never drift apart on WHICH
    fields are included -- only how they're rendered.
    """
    export = await build_account_export_data(db, current_user)
    csv_content = render_account_export_csv(export)

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=account-data-export.csv"},
    )

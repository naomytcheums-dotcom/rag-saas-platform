"""
Audit finding 27 -- enterprise SSO via generic OIDC (Azure AD, Okta, or
any other OIDC-conformant IdP). See api/models/enterprise_sso.py's module
docstring for why generic OIDC was chosen over SAML 2.0 (the spec
explicitly allows either), and api/security/enterprise_oidc.py's for why
this uses a fresh per-connection client rather than
api/routers/oauth.py's static, app-wide registry.

Two audiences, two sets of endpoints:
- Admins configure connections: POST/GET/DELETE /admin/sso/connections.
- Any (unauthenticated) visitor discovers and completes SSO login:
  POST /auth/sso/discover, GET /auth/sso/{connection_id}/authorize,
  GET /auth/sso/{connection_id}/callback.
"""

import asyncio
import datetime as dt
import logging
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.dependencies import get_db, require_admin
from api.models.audit_log import AuditAction
from api.models.enterprise_sso import EnterpriseSSOAccount, EnterpriseSSOConnection
from api.models.user import User
from api.schemas.enterprise_sso import (
    EnterpriseSSOConnectionCreateRequest,
    EnterpriseSSOConnectionEntry,
    EnterpriseSSOConnectionListResponse,
    SSODiscoverRequest,
    SSODiscoverResponse,
)
from api.security.audit_log import log_audit_action
from api.security.enterprise_oidc import build_client, fetch_oidc_metadata, verify_id_token
from api.security.jwt import create_mfa_pending_token
from api.security.secret_encryption import decrypt_secret, encrypt_secret
from api.security.sessions import issue_session
from api.security.webauthn import get_user_credentials
from api.services.email import send_enterprise_sso_connection_created_email
from api.utils import client_ip

router = APIRouter(tags=["auth"])
logger = logging.getLogger(__name__)

_INVALID_CONNECTION = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown or disabled SSO connection")
_SSO_LOGIN_FAILED = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enterprise SSO sign-in failed, please try again")


def _redirect_uri(connection_id: uuid.UUID) -> str:
    return f"{settings.OAUTH_REDIRECT_BASE_URL.rstrip('/')}/auth/sso/{connection_id}/callback"


def _email_domain(email: str) -> str:
    return email.rsplit("@", 1)[-1].lower()


async def _find_or_create_user(
    db: AsyncSession, connection: EnterpriseSSOConnection, provider_subject: str, email: str
) -> tuple[User, bool]:
    """
    Mirrors api/routers/oauth.py's _find_or_create_user almost exactly
    (same account-linking trust model: a verified IdP-asserted email is
    as good as this app's own OTP verification) -- with one addition
    that OAuth's fixed google/github providers don't need: the asserted
    email must actually belong to THIS connection's own email_domain.
    Without that check, a misconfigured IdP tenant (or a malicious insider
    with just enough access to mint a token for an unexpected email) could
    link or create an account for a completely unrelated address -- the
    entire point of scoping a connection to one domain in the first place.
    """
    if _email_domain(email) != connection.email_domain.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This identity provider is not authorized to sign in accounts for that email address",
        )

    sso_account = await db.scalar(
        select(EnterpriseSSOAccount).where(
            EnterpriseSSOAccount.connection_id == connection.id, EnterpriseSSOAccount.provider_subject == provider_subject
        )
    )
    if sso_account is not None:
        return await db.get(User, sso_account.user_id), False

    user = await db.scalar(select(User).where(User.email == email))
    is_new_user = user is None
    if user is None:
        user = User(email=email, hashed_password=None, is_email_verified=True)
        db.add(user)
        await db.flush()
    elif not user.is_email_verified:
        user.is_email_verified = True

    if user.consent_given_at is None:
        user.consent_given_at = dt.datetime.now(dt.timezone.utc)
        user.terms_version = settings.TERMS_VERSION

    db.add(EnterpriseSSOAccount(user_id=user.id, connection_id=connection.id, provider_subject=provider_subject, provider_email=email))
    await db.flush()
    return user, is_new_user


# ------------------------------------------------ admin configuration --

@router.post("/admin/sso/connections", response_model=EnterpriseSSOConnectionEntry, status_code=status.HTTP_201_CREATED)
async def create_sso_connection(
    payload: EnterpriseSSOConnectionCreateRequest, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    existing = await db.scalar(select(EnterpriseSSOConnection).where(EnterpriseSSOConnection.email_domain == payload.email_domain.lower()))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A connection for that email domain already exists")

    connection = EnterpriseSSOConnection(
        email_domain=payload.email_domain.lower(),
        display_name=payload.display_name,
        issuer=payload.issuer,
        client_id=payload.client_id,
        client_secret_encrypted=encrypt_secret(payload.client_secret),
        created_by_admin_id=admin.id,
    )
    db.add(connection)
    await log_audit_action(
        db, user_id=admin.id, action=AuditAction.ENTERPRISE_SSO_CONNECTION_CREATED, ip=None, user_agent=None,
        success=True, metadata={"email_domain": connection.email_domain, "issuer": connection.issuer},
    )
    await db.commit()

    try:
        await asyncio.to_thread(send_enterprise_sso_connection_created_email, admin.email, connection.email_domain, connection.display_name)
    except (EnvironmentError, RuntimeError) as exc:
        logger.warning("failed to send SSO-connection-created notification to %s: %s", admin.email, exc)

    return EnterpriseSSOConnectionEntry.model_validate(connection)


@router.get("/admin/sso/connections", response_model=EnterpriseSSOConnectionListResponse)
async def list_sso_connections(_admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(EnterpriseSSOConnection).order_by(EnterpriseSSOConnection.created_at.desc()))).all()
    return EnterpriseSSOConnectionListResponse(items=[EnterpriseSSOConnectionEntry.model_validate(r) for r in rows])


@router.delete("/admin/sso/connections/{connection_id}")
async def delete_sso_connection(connection_id: uuid.UUID, _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    connection = await db.get(EnterpriseSSOConnection, connection_id)
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await db.execute(delete(EnterpriseSSOConnection).where(EnterpriseSSOConnection.id == connection_id))
    await db.commit()
    return {"message": "SSO connection removed"}


# ------------------------------------------------------ public login ---

@router.post("/auth/sso/discover", response_model=SSODiscoverResponse)
async def discover_sso(payload: SSODiscoverRequest, db: AsyncSession = Depends(get_db)):
    """
    Public and unauthenticated by design -- lets a login screen show
    "Continue with <Company> SSO" as soon as an email is typed, before
    any password field even appears. Reveals only whether a domain has
    SSO configured (a company-level fact, not an individual account's
    existence) and a display name an admin chose specifically to be shown
    here -- not meaningfully more sensitive than a domain's public MX/SPF
    records, so no rate limiting is applied (unlike /auth/password/forgot,
    which would otherwise let this exact shape enumerate individual
    accounts, not just domains).
    """
    connection = await db.scalar(
        select(EnterpriseSSOConnection).where(
            EnterpriseSSOConnection.email_domain == _email_domain(payload.email), EnterpriseSSOConnection.is_enabled.is_(True),
        )
    )
    if connection is None:
        return SSODiscoverResponse(sso_available=False)
    return SSODiscoverResponse(sso_available=True, connection_id=connection.id, display_name=connection.display_name)


@router.get("/auth/sso/{connection_id}/authorize")
async def sso_authorize(connection_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)):
    connection = await db.get(EnterpriseSSOConnection, connection_id)
    if connection is None or not connection.is_enabled:
        raise _INVALID_CONNECTION

    try:
        metadata = await fetch_oidc_metadata(connection.issuer)
    except httpx.HTTPError as exc:
        logger.warning("failed to fetch OIDC metadata for SSO connection %s: %s", connection_id, exc)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="This identity provider is temporarily unreachable")

    client = build_client(connection.client_id, _redirect_uri(connection_id))
    authorization_url, state = client.create_authorization_url(metadata["authorization_endpoint"])

    # Stashed in the signed session cookie (same SessionMiddleware
    # api/routers/oauth.py's Authlib integration already relies on for
    # its own state) -- verified on the way back in sso_callback below,
    # the same CSRF protection Authlib's starlette client provides
    # automatically for Google/GitHub.
    request.session["enterprise_sso_state"] = state
    request.session["enterprise_sso_connection_id"] = str(connection_id)
    return RedirectResponse(url=authorization_url, status_code=status.HTTP_302_FOUND)


@router.get("/auth/sso/{connection_id}/callback")
async def sso_callback(
    connection_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db),
    code: str | None = Query(default=None), state: str | None = Query(default=None), error: str | None = Query(default=None),
):
    expected_connection_id = request.session.pop("enterprise_sso_connection_id", None)
    expected_state = request.session.pop("enterprise_sso_state", None)

    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Identity provider returned an error: {error}")
    if not code or not state or expected_state != state or expected_connection_id != str(connection_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired SSO login attempt, please try again")

    connection = await db.get(EnterpriseSSOConnection, connection_id)
    if connection is None or not connection.is_enabled:
        raise _INVALID_CONNECTION

    try:
        metadata = await fetch_oidc_metadata(connection.issuer)
        client_secret = decrypt_secret(connection.client_secret_encrypted)
        async with build_client(connection.client_id, _redirect_uri(connection_id), client_secret) as client:
            token = await client.fetch_token(metadata["token_endpoint"], code=code)
        id_token = token.get("id_token")
        if not id_token:
            raise _SSO_LOGIN_FAILED
        claims = await verify_id_token(id_token, metadata, connection.client_id, connection.issuer)
    except httpx.HTTPError as exc:
        logger.warning("SSO token exchange failed for connection %s: %s", connection_id, exc)
        raise _SSO_LOGIN_FAILED
    except Exception as exc:  # noqa: BLE001 -- covers PyJWT's various id_token validation errors (bad signature, wrong audience/issuer, expired) as one clean failure
        logger.warning("SSO id_token verification failed for connection %s: %s", connection_id, exc)
        raise _SSO_LOGIN_FAILED

    email = claims.get("email")
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Identity provider did not return an email address")
    # Self-critique, stated plainly rather than silently assumed away:
    # unlike api/routers/oauth.py's Google/GitHub checks, this does NOT
    # require claims.get("email_verified") -- Azure AD's v2.0 endpoint
    # does not reliably emit that claim at all for work/school accounts,
    # so requiring it would break real Azure AD tenants outright. The
    # email_domain scoping check in _find_or_create_user is this
    # connection's actual trust boundary instead: the admin who
    # configured issuer + client_id for THIS SPECIFIC domain already
    # vouches that this IdP is authoritative for it.

    user, is_new_user = await _find_or_create_user(db, connection, claims["sub"], email)

    webauthn_credentials = await get_user_credentials(db, user.id)
    if user.totp_enabled or webauthn_credentials:
        await db.commit()
        mfa_token = create_mfa_pending_token(user.id)
        methods = (["totp"] if user.totp_enabled else []) + (["webauthn"] if webauthn_credentials else [])
        redirect_url = (
            f"{settings.FRONTEND_URL.rstrip('/')}/oauth-callback#mfa_required=true&mfa_token={mfa_token}"
            f"&methods={','.join(methods)}"
        )
        return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)

    response = RedirectResponse(url=f"{settings.FRONTEND_URL.rstrip('/')}/oauth-callback", status_code=status.HTTP_302_FOUND)
    tokens = await issue_session(db, response, request, user.id, notify_new_device_email=None if is_new_user else user.email)
    await log_audit_action(
        db, user_id=user.id, action=AuditAction.ENTERPRISE_SSO_LOGIN_SUCCESS, ip=client_ip(request),
        user_agent=request.headers.get("user-agent"), success=True, metadata={"connection_id": str(connection_id)},
    )
    await db.commit()

    response.headers["location"] += f"#access_token={tokens.access_token}&expires_in={tokens.expires_in}"
    return response

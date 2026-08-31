"""
1.1.5 / 1.1.6 -- Google and GitHub via Authlib's Starlette client, which
handles the state/nonce/PKCE mechanics of the Authorization Code flow (the
part that's easy to get subtly wrong by hand). Requires SessionMiddleware
to be installed on the app (see api/main.py) -- that's where Authlib
stashes the state parameter between the /authorize redirect and the
/callback request.

Account linking: a provider-verified email is trusted to link to an
existing password-based account (find_or_create_user below) -- the
provider already proved the user controls that mailbox, which is exactly
what our own email-verification OTP (1.1.4) exists to prove for a
password signup. A brand new OAuth-only user gets hashed_password=None
and is_email_verified=True immediately, for the same reason.
"""

import logging

import httpx
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.database import AsyncSessionLocal
from api.models.oauth import OAuthAccount, OAuthProvider
from api.models.user import User
from api.security.sessions import issue_session

router = APIRouter(prefix="/auth/oauth", tags=["auth"])
logger = logging.getLogger(__name__)

oauth = OAuth()

if settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET:
    oauth.register(
        name="google",
        client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
        client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

if settings.GITHUB_OAUTH_CLIENT_ID and settings.GITHUB_OAUTH_CLIENT_SECRET:
    oauth.register(
        name="github",
        client_id=settings.GITHUB_OAUTH_CLIENT_ID,
        client_secret=settings.GITHUB_OAUTH_CLIENT_SECRET,
        access_token_url="https://github.com/login/oauth/access_token",
        authorize_url="https://github.com/login/oauth/authorize",
        api_base_url="https://api.github.com/",
        client_kwargs={"scope": "read:user user:email"},
    )

_SUPPORTED = {"google", "github"}


def _require_client(provider: str):
    if provider not in _SUPPORTED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown OAuth provider '{provider}'")
    client = oauth.create_client(provider)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"OAuth provider '{provider}' is not configured on this server",
        )
    return client


async def _fetch_google_identity(client, token) -> tuple[str, str]:
    userinfo = token.get("userinfo") or await client.userinfo(token=token)
    return str(userinfo["sub"]), userinfo["email"]


async def _fetch_github_identity(client, token) -> tuple[str, str]:
    profile_resp = await client.get("user", token=token)
    profile_resp.raise_for_status()
    profile = profile_resp.json()

    email = profile.get("email")
    if not email:
        # GitHub omits email from /user when the user has it set private --
        # the dedicated emails endpoint returns it regardless, scoped by
        # user:email, which we requested above.
        emails_resp = await client.get("user/emails", token=token)
        emails_resp.raise_for_status()
        primary = next((e for e in emails_resp.json() if e.get("primary") and e.get("verified")), None)
        if primary is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Your GitHub account has no verified, accessible email address",
            )
        email = primary["email"]

    return str(profile["id"]), email


_IDENTITY_FETCHERS = {"google": _fetch_google_identity, "github": _fetch_github_identity}


async def _find_or_create_user(db: AsyncSession, provider: OAuthProvider, provider_account_id: str, email: str) -> User:
    oauth_account = await db.scalar(
        select(OAuthAccount).where(
            OAuthAccount.provider == provider, OAuthAccount.provider_account_id == provider_account_id
        )
    )
    if oauth_account is not None:
        return await db.get(User, oauth_account.user_id)

    user = await db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, hashed_password=None, is_email_verified=True)
        db.add(user)
        await db.flush()

    db.add(OAuthAccount(user_id=user.id, provider=provider, provider_account_id=provider_account_id, provider_email=email))
    await db.flush()
    return user


@router.get("/{provider}/authorize")
async def oauth_authorize(provider: str, request: Request):
    client = _require_client(provider)
    redirect_uri = f"{settings.OAUTH_REDIRECT_BASE_URL.rstrip('/')}/auth/oauth/{provider}/callback"
    return await client.authorize_redirect(request, redirect_uri)


@router.get("/{provider}/callback")
async def oauth_callback(provider: str, request: Request):
    client = _require_client(provider)
    try:
        token = await client.authorize_access_token(request)
    except httpx.HTTPError as exc:
        logger.warning("OAuth token exchange failed for provider=%s: %s", provider, exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth sign-in failed, please try again")

    provider_account_id, email = await _IDENTITY_FETCHERS[provider](client, token)

    async with AsyncSessionLocal() as db:
        user = await _find_or_create_user(db, OAuthProvider(provider), provider_account_id, email)

        response = RedirectResponse(url=f"{settings.FRONTEND_URL.rstrip('/')}/oauth-callback", status_code=status.HTTP_302_FOUND)
        tokens = await issue_session(db, response, request, user.id)
        await db.commit()

    # The refresh token is already set as an httpOnly cookie by
    # issue_session(); the access token can't be, since the SPA needs to
    # read it into memory -- a URL fragment (never sent to the server,
    # never logged) is the standard way to hand a token to a redirect
    # target without putting it in server logs or the Referer header.
    response.headers["location"] += f"#access_token={tokens.access_token}&expires_in={tokens.expires_in}"
    return response

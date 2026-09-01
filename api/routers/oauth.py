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

2FA: proving identity to Google/GitHub is not the same as proving
possession of THIS account's second factor -- oauth_callback() checks
totp_enabled exactly like api/routers/auth.py's login() does, and routes
through the same MFA-pending hand-off to /2fa/verify-login instead of
issuing a session directly when it's enabled.
"""

import datetime as dt
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
from api.security.jwt import create_mfa_pending_token
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
    """Looks up the Authlib client for "google" or "github", registered
    above only if that provider's client_id/secret were actually
    configured. Returns a clean 503 (not a crash) if someone hits
    /auth/oauth/google/... on a server where Google credentials were
    never set."""
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
    """Returns (provider_account_id, email) for a just-authenticated
    Google user. `sub` is Google's own permanent, unique user id --
    that's what OAuthAccount.provider_account_id stores, not the email,
    because a Google account's email address can itself change later.

    1.1-audit finding, fixed: the presence of an `email` claim in
    Google's OIDC userinfo response does NOT by itself mean Google has
    verified that address -- `email_verified` is the claim that says so
    (OIDC Core 5.1), and this function previously never checked it. An
    account-linking flow that trusts an unverified email is exactly the
    account-takeover vector _find_or_create_user's docstring already
    warns about: link to an existing password account by email, no
    further proof required. The GitHub path right below already gets
    this right (filters on `verified` at line ~110); this brings Google
    to the same standard.
    """
    userinfo = token.get("userinfo") or await client.userinfo(token=token)
    if not userinfo.get("email_verified", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your Google account's email address is not verified",
        )
    return str(userinfo["sub"]), userinfo["email"]


async def _fetch_github_identity(client, token) -> tuple[str, str]:
    """Same idea as _fetch_google_identity, for GitHub -- GitHub's own
    numeric account id is the stable identifier; the email needs an
    extra API call in the common case where the user's GitHub email is
    set to private (see the comment below)."""
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


async def _find_or_create_user(db: AsyncSession, provider: OAuthProvider, provider_account_id: str, email: str) -> tuple[User, bool]:
    """
    Three possible outcomes, checked in order:
    1. This exact (provider, provider_account_id) has signed in before
       -> return that same user (returning OAuth user).
    2. No OAuthAccount yet, but a user with this email already exists
       (they signed up with a password originally) -> link this OAuth
       provider to that existing account, so either login method works
       from now on (account linking, see this module's top docstring for
       why trusting the provider's email here is safe).
    3. Neither -> brand new user, OAuth-only (no password set).
    Either way, a fresh OAuthAccount row is written before returning so
    case 1 applies on their next login.

    Returns (user, is_new_user) -- the caller uses is_new_user to decide
    whether a "new sign-in" notification makes sense (never for a
    brand-new account's very first session, same reasoning as
    register() in api/routers/auth.py).
    """
    oauth_account = await db.scalar(
        select(OAuthAccount).where(
            OAuthAccount.provider == provider, OAuthAccount.provider_account_id == provider_account_id
        )
    )
    if oauth_account is not None:
        return await db.get(User, oauth_account.user_id), False

    user = await db.scalar(select(User).where(User.email == email))
    is_new_user = user is None
    if user is None:
        user = User(email=email, hashed_password=None, is_email_verified=True)
        db.add(user)
        await db.flush()
    elif not user.is_email_verified:
        # Linking to a pre-existing, not-yet-verified account: the
        # provider just proved this person controls the mailbox, which is
        # exactly what 1.1.4's emailed OTP exists to prove for a password
        # signup -- so this is as good as them completing that flow, not
        # a separate, lesser form of verification.
        user.is_email_verified = True

    if user.consent_given_at is None:
        # register() captures this at the moment of an explicit
        # accept_terms=True; OAuth sign-up never shows that checkbox, so
        # without this, an OAuth-only account would have a permanently
        # empty RGPD consent record even though using the service is
        # itself an affirmative act. Only fills a gap -- never overwrites
        # a timestamp an existing password account already has from its
        # own real registration, so linking OAuth to an already-consented
        # account doesn't rewrite that history.
        user.consent_given_at = dt.datetime.now(dt.timezone.utc)
        user.terms_version = settings.TERMS_VERSION

    db.add(OAuthAccount(user_id=user.id, provider=provider, provider_account_id=provider_account_id, provider_email=email))
    await db.flush()
    return user, is_new_user


@router.get("/{provider}/authorize")
async def oauth_authorize(provider: str, request: Request):
    """
    "Sign in with Google/GitHub" button target -- a browser GET, not an
    API call an SPA would fetch() (it 302-redirects the whole page to
    Google/GitHub's own consent screen). Authlib builds that redirect
    URL, including the random `state` value it stashes in the session
    cookie to verify against on the way back in oauth_callback().
    """
    client = _require_client(provider)
    redirect_uri = f"{settings.OAUTH_REDIRECT_BASE_URL.rstrip('/')}/auth/oauth/{provider}/callback"
    return await client.authorize_redirect(request, redirect_uri)


@router.get("/{provider}/callback")
async def oauth_callback(provider: str, request: Request):
    """
    Where Google/GitHub redirects the browser back to after the user
    approves (or denies) access. Authlib's authorize_access_token()
    verifies the `state` matches what /authorize stashed (rejecting a
    forged callback that skipped the real consent screen) and exchanges
    the provider's one-time code for an actual access token, which is
    then used once to fetch the user's identity and immediately
    discarded -- see this module's top docstring on why nothing from the
    provider is persisted beyond the account id and email.
    """
    client = _require_client(provider)
    try:
        token = await client.authorize_access_token(request)
    except httpx.HTTPError as exc:
        logger.warning("OAuth token exchange failed for provider=%s: %s", provider, exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth sign-in failed, please try again")

    provider_account_id, email = await _IDENTITY_FETCHERS[provider](client, token)

    async with AsyncSessionLocal() as db:
        user, is_new_user = await _find_or_create_user(db, OAuthProvider(provider), provider_account_id, email)

        if user.totp_enabled:
            # The provider proved WHO this person is, not that they hold
            # this account's second factor -- an account that enabled 2FA
            # through the password flow (api/routers/auth.py's login())
            # must not have that requirement quietly skipped just because
            # it also has a linked Google/GitHub sign-in. Same mfa_token
            # hand-off as a password login: no session is issued here,
            # the frontend must follow up with POST /auth/2fa/verify-login
            # (or /verify-recovery-code) exactly as it would after a
            # password login that returned MFARequiredResponse.
            await db.commit()  # persists _find_or_create_user's writes (new/updated OAuthAccount link, consent backfill, etc.) even though no session is issued this request
            mfa_token = create_mfa_pending_token(user.id)
            redirect_url = f"{settings.FRONTEND_URL.rstrip('/')}/oauth-callback#mfa_required=true&mfa_token={mfa_token}"
            return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)

        response = RedirectResponse(url=f"{settings.FRONTEND_URL.rstrip('/')}/oauth-callback", status_code=status.HTTP_302_FOUND)
        tokens = await issue_session(
            db, response, request, user.id,
            notify_new_device_email=None if is_new_user else user.email,
        )
        await db.commit()

    # The refresh token is already set as an httpOnly cookie by
    # issue_session(); the access token can't be, since the SPA needs to
    # read it into memory -- a URL fragment (never sent to the server,
    # never logged) is the standard way to hand a token to a redirect
    # target without putting it in server logs or the Referer header.
    # Same reasoning applies to mfa_token above -- it's short-lived and
    # single-purpose, but still worth keeping out of server logs.
    response.headers["location"] += f"#access_token={tokens.access_token}&expires_in={tokens.expires_in}"
    return response

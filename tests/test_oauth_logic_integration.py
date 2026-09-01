"""
1.1.5 / 1.1.6 -- tests the account find-or-create logic in
api/routers/oauth.py directly against real Postgres, without going
through a real browser/provider consent screen (which nothing can
automate -- see docs/AUTH_BACKEND_SETUP.md's "What is NOT automated"
section). This is the part of OAuth that's genuinely testable end to end
without a human: given a (provider, provider_account_id, email) tuple --
exactly what a real callback would have extracted from Google/GitHub --
does the right thing happen in the database.
"""

import datetime as dt
import uuid

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.models.oauth import OAuthAccount, OAuthProvider
from api.models.user import User
from api.routers.oauth import _find_or_create_user
from api.security.hashing import hash_password

# Loop scope defaults to "session" globally (pyproject.toml); no override needed here.


@pytest.fixture(scope="module")
async def pg_engine():
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"DATABASE_URL is not reachable -- skipping OAuth logic integration tests ({exc})")
    yield engine
    await engine.dispose()


@pytest.fixture
async def pg_session(pg_engine):
    session_factory = async_sessionmaker(bind=pg_engine, expire_on_commit=False, autoflush=False)
    async with session_factory() as session:
        yield session


def _unique_email() -> str:
    return f"oauth-logic-{uuid.uuid4().hex[:10]}@example.com"


async def test_brand_new_oauth_user_is_created_and_pre_verified(pg_session):
    email = _unique_email()
    provider_account_id = uuid.uuid4().hex

    try:
        user, is_new_user = await _find_or_create_user(pg_session, OAuthProvider.google, provider_account_id, email)
        await pg_session.commit()

        assert is_new_user is True
        assert user.email == email
        assert user.hashed_password is None  # OAuth-only account, no password ever set
        assert user.is_email_verified is True  # the provider already proved mailbox ownership
        assert user.consent_given_at is not None  # no accept_terms checkbox in this flow -- see _find_or_create_user's fix
        assert user.terms_version == settings.TERMS_VERSION

        linked = await pg_session.scalar(select(OAuthAccount).where(OAuthAccount.user_id == user.id))
        assert linked.provider == OAuthProvider.google
        assert linked.provider_account_id == provider_account_id
    finally:
        await pg_session.execute(delete(User).where(User.email == email))
        await pg_session.commit()


async def test_oauth_links_to_existing_unverified_account_and_verifies_it(pg_session):
    """This is the exact bug found and fixed while manually testing real
    Google login: linking to a pre-existing password account used to
    leave is_email_verified False even though the provider just proved
    the same thing 1.1.4's OTP flow exists to prove."""
    email = _unique_email()
    existing_user = User(email=email, hashed_password=hash_password("some-password"), is_email_verified=False)
    pg_session.add(existing_user)
    await pg_session.flush()
    existing_user_id = existing_user.id

    try:
        linked_user, is_new_user = await _find_or_create_user(pg_session, OAuthProvider.github, uuid.uuid4().hex, email)
        await pg_session.commit()

        assert is_new_user is False  # linked to a pre-existing account, not created fresh
        assert linked_user.id == existing_user_id  # linked to the SAME account, not a new one
        assert linked_user.hashed_password is not None  # password login must still work too
        assert linked_user.is_email_verified is True  # the fix: now flipped by the OAuth link
        assert linked_user.consent_given_at is not None  # backfilled -- this fixture's user had none set
    finally:
        await pg_session.execute(delete(User).where(User.email == email))
        await pg_session.commit()


async def test_oauth_linking_does_not_overwrite_an_existing_consent_record(pg_session):
    """The backfill in _find_or_create_user must never clobber a real
    registration's consent_given_at -- that timestamp is a compliance
    record of when the user actually agreed (api/models/user.py's
    docstring), and OAuth linking happening later must not silently
    rewrite it to "just now"."""
    email = _unique_email()
    original_consent_time = dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc)
    existing_user = User(
        email=email, hashed_password=hash_password("some-password"), is_email_verified=True,
        consent_given_at=original_consent_time, terms_version="2020-01-01",
    )
    pg_session.add(existing_user)
    await pg_session.flush()

    try:
        linked_user, _ = await _find_or_create_user(pg_session, OAuthProvider.google, uuid.uuid4().hex, email)
        await pg_session.commit()

        assert linked_user.consent_given_at == original_consent_time
        assert linked_user.terms_version == "2020-01-01"
    finally:
        await pg_session.execute(delete(User).where(User.email == email))
        await pg_session.commit()


async def test_oauth_does_not_unverify_an_already_verified_account(pg_session):
    email = _unique_email()
    existing_user = User(email=email, hashed_password=hash_password("some-password"), is_email_verified=True)
    pg_session.add(existing_user)
    await pg_session.flush()

    try:
        linked_user, _ = await _find_or_create_user(pg_session, OAuthProvider.google, uuid.uuid4().hex, email)
        await pg_session.commit()
        assert linked_user.is_email_verified is True
    finally:
        await pg_session.execute(delete(User).where(User.email == email))
        await pg_session.commit()


async def test_oauth_callback_requires_2fa_when_the_account_has_it_enabled(pg_session, monkeypatch):
    """
    The real bug found while auditing this module: oauth_callback() used
    to call issue_session() unconditionally, so an account with 2FA
    enabled through the password flow (api/routers/auth.py's login())
    could bypass it entirely by signing in through a linked Google/GitHub
    account instead -- the provider proves WHO the user is, not that they
    hold this app's own second factor.

    A real browser consent screen can't be automated (see this file's top
    docstring), but the token EXCHANGE step can be faked at its two
    integration points (_require_client, _IDENTITY_FETCHERS) -- same
    "fake the external call, keep everything else real" approach this
    suite already uses for Resend emails -- which lets this drive the
    actual GET /auth/oauth/google/callback route, against real Postgres,
    instead of only testing _find_or_create_user() in isolation like the
    tests above.
    """
    import api.routers.oauth as oauth_module
    from api.main import app
    from api.security.hashing import hash_password
    from api.security.jwt import TokenPurpose, decode_token
    from httpx import ASGITransport, AsyncClient

    email = _unique_email()
    user = User(
        email=email, hashed_password=hash_password("some-password"), is_email_verified=True,
        totp_enabled=True, totp_secret="JBSWY3DPEHPK3PXP",
    )
    pg_session.add(user)
    await pg_session.commit()
    user_id = user.id

    class _FakeOAuthClient:
        async def authorize_access_token(self, request):
            return {}

    monkeypatch.setattr(oauth_module, "_require_client", lambda provider: _FakeOAuthClient())

    async def _fake_identity(client, token):
        return "fake-provider-account-id-for-this-test", email

    monkeypatch.setattr(oauth_module, "_IDENTITY_FETCHERS", {"google": _fake_identity, "github": _fake_identity})

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/auth/oauth/google/callback", follow_redirects=False)

        assert response.status_code == 302
        location = response.headers["location"]
        assert "mfa_required=true" in location  # sent to the MFA step, not logged straight in
        assert "access_token=" not in location  # the critical assertion: no session was issued
        assert "mfa_token=" in location

        mfa_token = location.split("mfa_token=")[1]
        assert decode_token(mfa_token, TokenPurpose.MFA_PENDING).user_id == user_id  # a real, usable MFA-pending token for THIS user
    finally:
        await pg_session.execute(delete(User).where(User.email == email))
        await pg_session.commit()


async def test_oauth_callback_issues_a_session_directly_when_2fa_is_not_enabled(pg_session, monkeypatch):
    """Companion to the test above -- guards against a regression in the
    other direction: the vast majority of accounts don't have 2FA
    enabled, and those must keep getting a real access token straight
    from the callback, not an unnecessary MFA detour."""
    import api.routers.oauth as oauth_module
    from api.main import app
    from httpx import ASGITransport, AsyncClient

    email = _unique_email()

    class _FakeOAuthClient:
        async def authorize_access_token(self, request):
            return {}

    monkeypatch.setattr(oauth_module, "_require_client", lambda provider: _FakeOAuthClient())

    async def _fake_identity(client, token):
        return "fake-provider-account-id-for-this-test-2", email

    monkeypatch.setattr(oauth_module, "_IDENTITY_FETCHERS", {"google": _fake_identity, "github": _fake_identity})

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/auth/oauth/google/callback", follow_redirects=False)

            assert response.status_code == 302
            location = response.headers["location"]
            assert "access_token=" in location
            assert "mfa_required" not in location

            # 1.1.15: NOT assumed just because oauth_callback() calls the
            # same issue_session() every other login path uses -- proven
            # directly, against real Postgres. The OAuth-issued access
            # token must be genuinely blacklistable, not a special case
            # that silently skipped access_token_jti.
            oauth_access_token = location.split("access_token=")[1].split("&")[0]
            auth_header = {"Authorization": f"Bearer {oauth_access_token}"}

            still_valid = await client.get("/account/me", headers=auth_header)
            assert still_valid.status_code == 200

            logout = await client.post("/auth/logout", headers={"X-CSRF-Token": client.cookies.get("csrf_token") or ""})
            assert logout.status_code == 200

            now_blacklisted = await client.get("/account/me", headers=auth_header)
            assert now_blacklisted.status_code == 401
    finally:
        await pg_session.execute(delete(User).where(User.email == email))
        await pg_session.commit()


async def test_google_identity_fetch_rejects_an_unverified_email():
    """1.1-audit finding, fixed: Google's OIDC userinfo response can
    include an `email` claim without `email_verified` being true --
    trusting it anyway for account linking (_find_or_create_user links
    to an EXISTING account by email with no further proof) would be a
    real account-takeover vector. No DB/network needed -- _fetch_google_identity
    only reads the token dict it's handed, so this is tested directly
    without pg_session's real-Postgres fixture."""
    from fastapi import HTTPException

    from api.routers.oauth import _fetch_google_identity

    fake_token = {"userinfo": {"sub": "12345", "email": "victim@example.com", "email_verified": False}}
    try:
        await _fetch_google_identity(client=None, token=fake_token)
        assert False, "expected HTTPException for an unverified email"
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "not verified" in exc.detail


async def test_google_identity_fetch_accepts_a_verified_email():
    from api.routers.oauth import _fetch_google_identity

    fake_token = {"userinfo": {"sub": "12345", "email": "real-user@example.com", "email_verified": True}}
    provider_account_id, email = await _fetch_google_identity(client=None, token=fake_token)
    assert provider_account_id == "12345"
    assert email == "real-user@example.com"


class _FakeHttpResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeGithubClient:
    """Coverage audit finding: _fetch_github_identity's real body was
    NEVER exercised by any existing test -- every OAuth-callback test
    monkeypatches _IDENTITY_FETCHERS itself with a stub, bypassing the
    real GitHub-calling logic entirely (private-email fallback, the
    "no verified email at all" rejection). Tested directly here with a
    fake httpx-shaped client, no real network."""

    def __init__(self, profile, emails=None):
        self._profile = profile
        self._emails = emails

    async def get(self, path, token):
        if path == "user":
            return _FakeHttpResponse(self._profile)
        if path == "user/emails":
            return _FakeHttpResponse(self._emails)
        raise AssertionError(f"unexpected path {path}")


async def test_github_identity_fetch_uses_the_public_email_when_present():
    from api.routers.oauth import _fetch_github_identity

    client = _FakeGithubClient(profile={"id": 999, "email": "public@example.com"})
    provider_account_id, email = await _fetch_github_identity(client, token={})
    assert provider_account_id == "999"
    assert email == "public@example.com"


async def test_github_identity_fetch_falls_back_to_the_verified_primary_email_when_private():
    """GitHub omits `email` from /user when the user has it set private
    -- the dedicated /user/emails endpoint is the fallback, filtered to
    the primary AND verified entry specifically."""
    from api.routers.oauth import _fetch_github_identity

    client = _FakeGithubClient(
        profile={"id": 999, "email": None},
        emails=[
            {"email": "secondary@example.com", "primary": False, "verified": True},
            {"email": "unverified-primary@example.com", "primary": True, "verified": False},
            {"email": "the-real-one@example.com", "primary": True, "verified": True},
        ],
    )
    provider_account_id, email = await _fetch_github_identity(client, token={})
    assert email == "the-real-one@example.com"


async def test_github_identity_fetch_rejects_an_account_with_no_verified_accessible_email():
    from fastapi import HTTPException

    from api.routers.oauth import _fetch_github_identity

    client = _FakeGithubClient(profile={"id": 999, "email": None}, emails=[{"email": "x@example.com", "primary": True, "verified": False}])
    try:
        await _fetch_github_identity(client, token={})
        assert False, "expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "no verified" in exc.detail.lower()


async def test_require_client_rejects_an_unsupported_provider():
    from fastapi import HTTPException

    from api.routers.oauth import _require_client

    try:
        _require_client("facebook")
        assert False, "expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 404


async def test_require_client_returns_503_when_the_provider_is_not_configured(monkeypatch):
    """Coverage audit finding: never exercised -- both providers ARE
    configured in this project's real .env, so create_client("google")
    never actually returns None under normal test settings. The
    registration itself happens once at import time, so this monkeypatches
    create_client directly rather than trying to un-configure settings
    after the fact."""
    import api.routers.oauth as oauth_module
    from fastapi import HTTPException

    monkeypatch.setattr(oauth_module.oauth, "create_client", lambda provider: None)
    try:
        oauth_module._require_client("google")
        assert False, "expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 503


async def test_oauth_authorize_redirects_to_the_real_provider_consent_screen():
    """Never previously tested at all -- every other OAuth test targets
    /callback. Just the redirect construction: no real consent screen
    is reached, but Authlib should still build a real redirect Location
    pointing at Google's actual authorization endpoint."""
    from httpx import ASGITransport, AsyncClient

    from api.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/auth/oauth/google/authorize", follow_redirects=False)

    assert response.status_code == 302
    assert "accounts.google.com" in response.headers["location"]


async def test_oauth_callback_wraps_a_token_exchange_failure_as_a_400(monkeypatch):
    """Coverage audit finding: oauth_callback's own httpx.HTTPError catch
    around authorize_access_token -- e.g. the provider's token endpoint
    being unreachable/erroring during the code-for-token exchange --
    had never been exercised."""
    import httpx as httpx_module
    from httpx import ASGITransport, AsyncClient

    import api.routers.oauth as oauth_module
    from api.main import app

    class _FailingOAuthClient:
        async def authorize_access_token(self, request):
            raise httpx_module.ConnectError("simulated provider outage")

    monkeypatch.setattr(oauth_module, "_require_client", lambda provider: _FailingOAuthClient())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/auth/oauth/google/callback", follow_redirects=False)

    assert response.status_code == 400
    assert "sign-in failed" in response.json()["detail"].lower()


async def test_returning_oauth_user_reuses_the_same_account_no_duplicate_link(pg_session):
    email = _unique_email()
    provider_account_id = uuid.uuid4().hex

    try:
        first_login, first_is_new = await _find_or_create_user(pg_session, OAuthProvider.google, provider_account_id, email)
        await pg_session.commit()

        second_login, second_is_new = await _find_or_create_user(pg_session, OAuthProvider.google, provider_account_id, email)
        await pg_session.commit()

        assert first_is_new is True
        assert second_is_new is False  # same OAuthAccount matched -- not a new user
        assert first_login.id == second_login.id

        link_count = len((await pg_session.scalars(select(OAuthAccount).where(OAuthAccount.user_id == first_login.id))).all())
        assert link_count == 1  # no duplicate OAuthAccount row created on the second login
    finally:
        await pg_session.execute(delete(User).where(User.email == email))
        await pg_session.commit()

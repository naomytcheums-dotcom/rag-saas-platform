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
        user = await _find_or_create_user(pg_session, OAuthProvider.google, provider_account_id, email)
        await pg_session.commit()

        assert user.email == email
        assert user.hashed_password is None  # OAuth-only account, no password ever set
        assert user.is_email_verified is True  # the provider already proved mailbox ownership

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
        linked_user = await _find_or_create_user(pg_session, OAuthProvider.github, uuid.uuid4().hex, email)
        await pg_session.commit()

        assert linked_user.id == existing_user_id  # linked to the SAME account, not a new one
        assert linked_user.hashed_password is not None  # password login must still work too
        assert linked_user.is_email_verified is True  # the fix: now flipped by the OAuth link
    finally:
        await pg_session.execute(delete(User).where(User.email == email))
        await pg_session.commit()


async def test_oauth_does_not_unverify_an_already_verified_account(pg_session):
    email = _unique_email()
    existing_user = User(email=email, hashed_password=hash_password("some-password"), is_email_verified=True)
    pg_session.add(existing_user)
    await pg_session.flush()

    try:
        linked_user = await _find_or_create_user(pg_session, OAuthProvider.google, uuid.uuid4().hex, email)
        await pg_session.commit()
        assert linked_user.is_email_verified is True
    finally:
        await pg_session.execute(delete(User).where(User.email == email))
        await pg_session.commit()


async def test_returning_oauth_user_reuses_the_same_account_no_duplicate_link(pg_session):
    email = _unique_email()
    provider_account_id = uuid.uuid4().hex

    try:
        first_login = await _find_or_create_user(pg_session, OAuthProvider.google, provider_account_id, email)
        await pg_session.commit()

        second_login = await _find_or_create_user(pg_session, OAuthProvider.google, provider_account_id, email)
        await pg_session.commit()

        assert first_login.id == second_login.id

        link_count = len((await pg_session.scalars(select(OAuthAccount).where(OAuthAccount.user_id == first_login.id))).all())
        assert link_count == 1  # no duplicate OAuthAccount row created on the second login
    finally:
        await pg_session.execute(delete(User).where(User.email == email))
        await pg_session.commit()

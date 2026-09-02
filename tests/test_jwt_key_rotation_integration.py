"""
Audit finding 28, tested against the REAL Postgres database in
DATABASE_URL -- same reasoning and same pg_engine/skip-if-unreachable
pattern as tests/test_postgres_integration.py and
tests/test_celery_integration.py (the Celery task itself is exercised via
`.apply().get()`, same as every other task in that file: runs the task
body synchronously in this process, no broker/worker needed).

Every test starts by deleting every row from jwt_signing_keys -- a table
this feature owns exclusively (nothing else in the app writes to it), so
a clean slate per test is safe the same way
test_rate_limiting_integration.py's _enable_rate_limiting fixture safely
flushes its own dedicated Redis DB.
"""

import asyncio
import datetime as dt
import uuid

import jwt as pyjwt
import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.config import settings
from api.models.jwt_signing_key import JWTSigningKey
from api.security import jwt as jwt_module
from api.security.jwt import (
    TokenPurpose,
    create_access_token,
    decode_token,
    refresh_jwt_key_cache,
)
from api.security.secret_encryption import encrypt_secret
from api.tasks.jwt_key_rotation import rotate_jwt_signing_key


@pytest.fixture(scope="module")
async def pg_engine():
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"DATABASE_URL is not reachable -- skipping JWT key rotation integration tests ({exc})")
    yield engine
    await engine.dispose()


@pytest.fixture
async def pg_session(pg_engine):
    session_factory = async_sessionmaker(bind=pg_engine, expire_on_commit=False, autoflush=False)
    async with session_factory() as session:
        yield session


@pytest.fixture(autouse=True)
async def _clean_jwt_signing_keys_table(pg_engine):
    session_factory = async_sessionmaker(bind=pg_engine, expire_on_commit=False, autoflush=False)
    async with session_factory() as session:
        await session.execute(delete(JWTSigningKey))
        await session.commit()
    yield
    async with session_factory() as session:
        await session.execute(delete(JWTSigningKey))
        await session.commit()


@pytest.fixture(autouse=True)
def _reset_jwt_key_cache_and_settings(monkeypatch):
    """The in-memory cache (api/security/jwt.py's module-level
    _key_cache) must not leak a DB-backed key from one test into the
    next, and JWT_AUTO_ROTATION_INTERVAL_DAYS defaults to 0 (disabled)
    for the whole rest of the suite -- each test that needs rotation
    ENABLED sets this explicitly."""
    monkeypatch.setattr(jwt_module, "_key_cache", {"active_secret": None, "verification_secrets": []})
    monkeypatch.setattr(settings, "JWT_AUTO_ROTATION_INTERVAL_DAYS", 0)
    monkeypatch.setattr(settings, "JWT_KEY_RETENTION_DAYS", 7)
    monkeypatch.setattr(settings, "JWT_KEY_ROTATION_ADMIN_EMAIL", None)
    if not settings.SECRET_ENCRYPTION_KEY:
        from cryptography.fernet import Fernet
        monkeypatch.setattr(settings, "SECRET_ENCRYPTION_KEY", Fernet.generate_key().decode())


# -------------------------------------------------- rotation task ------

async def test_rotation_is_disabled_by_default(pg_session):
    """JWT_AUTO_ROTATION_INTERVAL_DAYS=0 (the untouched default from
    _reset_jwt_key_cache_and_settings above) must make every run a
    guaranteed no-op -- the property that lets this feature's beat_schedule
    entry stay registered unconditionally (see celery_app.py's comment)."""
    rotated = rotate_jwt_signing_key.apply().get()
    assert rotated is False
    rows = (await pg_session.scalars(select(JWTSigningKey))).all()
    assert rows == []


async def test_rotation_bootstraps_the_first_key_when_none_exists(monkeypatch, pg_session):
    monkeypatch.setattr(settings, "JWT_AUTO_ROTATION_INTERVAL_DAYS", 30)

    rotated = rotate_jwt_signing_key.apply().get()
    assert rotated is True

    rows = (await pg_session.scalars(select(JWTSigningKey))).all()
    assert len(rows) == 1
    assert rows[0].is_active is True
    assert rows[0].retired_at is None


async def test_rotation_is_a_no_op_when_the_current_key_is_not_yet_due(monkeypatch, pg_session):
    monkeypatch.setattr(settings, "JWT_AUTO_ROTATION_INTERVAL_DAYS", 30)
    pg_session.add(JWTSigningKey(secret=encrypt_secret("current-key"), is_active=True))
    await pg_session.commit()

    rotated = rotate_jwt_signing_key.apply().get()
    assert rotated is False

    rows = (await pg_session.scalars(select(JWTSigningKey))).all()
    assert len(rows) == 1  # no new key created


async def test_rotation_retires_the_old_key_and_activates_a_new_one_when_due(monkeypatch, pg_engine, pg_session):
    monkeypatch.setattr(settings, "JWT_AUTO_ROTATION_INTERVAL_DAYS", 30)
    overdue_created_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=31)
    old_key = JWTSigningKey(secret=encrypt_secret("old-key"), is_active=True, created_at=overdue_created_at)
    pg_session.add(old_key)
    await pg_session.commit()
    old_key_id = old_key.id

    rotated = rotate_jwt_signing_key.apply().get()
    assert rotated is True

    # Read back through a BRAND NEW session, not pg_session -- pg_session
    # already has `old_key` in its identity map from the add() above, and
    # the rotation task mutated that same row through an entirely
    # separate (sync) session/connection. A plain select() on an
    # already-identity-mapped object does not overwrite its cached
    # attributes by default, so re-querying via pg_session here would
    # silently see the STALE pre-rotation is_active=True for that row --
    # exactly the kind of cross-session staleness
    # tests/test_celery_integration.py's own Core-style (non-ORM-session)
    # reads are designed to sidestep for the same reason.
    async with async_sessionmaker(bind=pg_engine, expire_on_commit=False)() as fresh_session:
        rows = (await fresh_session.scalars(select(JWTSigningKey))).all()

    assert len(rows) == 2
    active = [r for r in rows if r.is_active]
    retired = [r for r in rows if not r.is_active]
    assert len(active) == 1
    assert len(retired) == 1
    assert retired[0].id == old_key_id
    assert retired[0].retired_at is not None


async def test_rotation_is_idempotent_within_the_same_interval(monkeypatch, pg_session):
    monkeypatch.setattr(settings, "JWT_AUTO_ROTATION_INTERVAL_DAYS", 30)

    first = rotate_jwt_signing_key.apply().get()
    second = rotate_jwt_signing_key.apply().get()
    assert first is True
    assert second is False  # the key `first` just created isn't due yet

    rows = (await pg_session.scalars(select(JWTSigningKey))).all()
    assert len(rows) == 1


async def test_rotation_sends_the_admin_notification_email_only_when_configured(monkeypatch, pg_session):
    captured = []
    monkeypatch.setattr("api.tasks.jwt_key_rotation.send_jwt_key_rotated_email", lambda *a, **kw: captured.append((a, kw)))
    monkeypatch.setattr(settings, "JWT_AUTO_ROTATION_INTERVAL_DAYS", 30)

    rotate_jwt_signing_key.apply().get()
    assert captured == []  # JWT_KEY_ROTATION_ADMIN_EMAIL unset -- no email

    await pg_session.execute(delete(JWTSigningKey))
    await pg_session.commit()
    monkeypatch.setattr(settings, "JWT_KEY_ROTATION_ADMIN_EMAIL", "security-team@example.com")

    rotate_jwt_signing_key.apply().get()
    assert len(captured) == 1
    assert captured[0][0][0] == "security-team@example.com"


async def test_rotation_leaves_the_key_creatable_even_when_the_admin_email_fails(monkeypatch, pg_session):
    """The same non-fatal-email pattern used throughout this codebase
    (e.g. api/security/sessions.py's notification sends): a Resend outage
    while sending the rotation notice must not make the task report
    failure or roll back the rotation itself, which already committed."""
    monkeypatch.setattr(settings, "JWT_AUTO_ROTATION_INTERVAL_DAYS", 30)
    monkeypatch.setattr(settings, "JWT_KEY_ROTATION_ADMIN_EMAIL", "security-team@example.com")

    def _raise(*a, **kw):
        raise RuntimeError("Resend is unreachable (simulated)")

    monkeypatch.setattr("api.tasks.jwt_key_rotation.send_jwt_key_rotated_email", _raise)

    rotated = rotate_jwt_signing_key.apply().get()
    assert rotated is True  # the rotation itself still succeeded

    rows = (await pg_session.scalars(select(JWTSigningKey))).all()
    assert len(rows) == 1
    assert rows[0].is_active is True


# -------------------------------------------------- key cache ----------

async def test_a_token_signed_before_a_refresh_still_decodes_after_it(pg_session):
    """The property that makes rotation SAFE, not just "automatic": a
    token signed under the OLD (env-based) key before the cache was ever
    populated must still decode correctly once a DB-backed key becomes
    active -- decode_token()'s multi-key trial loop, not signing key
    identity, is what makes that true."""
    user_id = uuid.uuid4()
    token, _jti = create_access_token(user_id)

    pg_session.add(JWTSigningKey(secret=encrypt_secret("a-brand-new-db-backed-secret"), is_active=True))
    await pg_session.commit()
    await refresh_jwt_key_cache(pg_session)

    decoded = decode_token(token, TokenPurpose.ACCESS)
    assert decoded.user_id == user_id


async def test_new_tokens_are_signed_with_the_db_backed_active_key_once_cached(pg_session):
    """Once the cache is populated, NEW tokens are signed with the
    DB-backed key, not JWT_SECRET_KEY -- proven by decoding with pyjwt
    directly against the known plaintext secret, bypassing this app's own
    (multi-key-trying) decode_token()."""
    known_secret = "a-known-plaintext-secret-for-this-test-only"
    pg_session.add(JWTSigningKey(secret=encrypt_secret(known_secret), is_active=True))
    await pg_session.commit()
    await refresh_jwt_key_cache(pg_session)

    token, _jti = create_access_token(uuid.uuid4())
    payload = pyjwt.decode(token, known_secret, algorithms=[settings.JWT_ALGORITHM])
    assert payload["purpose"] == "access"


async def test_a_retired_key_still_verifies_within_its_retention_window(monkeypatch, pg_session):
    monkeypatch.setattr(settings, "JWT_AUTO_ROTATION_INTERVAL_DAYS", 30)
    monkeypatch.setattr(settings, "JWT_KEY_RETENTION_DAYS", 7)

    pg_session.add(JWTSigningKey(secret=encrypt_secret("first-active-key"), is_active=True))
    await pg_session.commit()
    await refresh_jwt_key_cache(pg_session)

    token, _jti = create_access_token(uuid.uuid4())  # signed with "first-active-key"

    # Force a rotation -- "first-active-key" is retired, a new key becomes active.
    rows = (await pg_session.scalars(select(JWTSigningKey))).all()
    rows[0].created_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=31)
    await pg_session.commit()
    rotate_jwt_signing_key.apply().get()

    await refresh_jwt_key_cache(pg_session)
    # The OLD token must still decode -- its signing key is retired, not gone.
    decoded = decode_token(token, TokenPurpose.ACCESS)
    assert decoded is not None


async def test_a_key_retired_past_its_retention_window_no_longer_verifies(pg_session):
    retired_secret = "a-long-retired-secret-past-its-retention-window"
    old_key = JWTSigningKey(
        secret=encrypt_secret(retired_secret), is_active=False,
        retired_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=settings.JWT_KEY_RETENTION_DAYS + 1),
    )
    pg_session.add(old_key)
    # An unrelated active key must exist too, otherwise decode_token would
    # fall back to JWT_SECRET_KEY/JWT_PREVIOUS_SECRET_KEYS and this test
    # would prove nothing about retention filtering specifically.
    pg_session.add(JWTSigningKey(secret=encrypt_secret("current-unrelated-key"), is_active=True))
    await pg_session.commit()

    await refresh_jwt_key_cache(pg_session)

    stale_token = pyjwt.encode(
        {"sub": "00000000-0000-0000-0000-000000000000", "jti": "x", "purpose": "access",
         "iat": dt.datetime.now(dt.timezone.utc), "exp": dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5)},
        retired_secret, algorithm=settings.JWT_ALGORITHM,
    )
    with pytest.raises(pyjwt.InvalidSignatureError):
        decode_token(stale_token, TokenPurpose.ACCESS)


async def test_a_db_failure_during_refresh_leaves_the_existing_cache_untouched(monkeypatch, pg_session):
    """api/security/jwt.py's refresh_jwt_key_cache must fail open -- a
    transient Postgres blip must not suddenly make a process unable to
    verify tokens it could verify a moment ago."""
    pg_session.add(JWTSigningKey(secret=encrypt_secret("a-working-secret"), is_active=True))
    await pg_session.commit()
    await refresh_jwt_key_cache(pg_session)
    assert jwt_module._key_cache["active_secret"] == "a-working-secret"

    class _BrokenSession:
        async def scalars(self, *a, **kw):
            raise ConnectionError("simulated Postgres outage")

    await refresh_jwt_key_cache(_BrokenSession())  # must not raise
    assert jwt_module._key_cache["active_secret"] == "a-working-secret"  # unchanged


# -------------------------------------------------- app lifespan -------

async def test_the_running_apps_lifespan_picks_up_a_new_key_without_a_restart(monkeypatch, pg_engine):
    """
    The actual end-to-end claim behind "automatic" (this module's top
    docstring, api/main.py's lifespan docstring): a key written to
    Postgres by something else entirely (here, a plain insert standing in
    for api/tasks/jwt_key_rotation.py's Celery Beat run) is picked up by
    an ALREADY-RUNNING API process's background poll loop, with no
    restart and no direct call to refresh_jwt_key_cache from this test.
    Uses api.main's real lifespan and api.database's real AsyncSessionLocal
    (both bound to the same DATABASE_URL as pg_engine) -- not a
    reimplementation of the polling loop.
    """
    # 1s, not a few ms: this hits the REAL Supabase pooler over the real
    # network, and a single connection+query round trip there was
    # measured (while diagnosing this exact test) at ~1-2s wall-clock --
    # far slower than a local Postgres. A short fixed sleep after that
    # made this test flaky for pure timing reasons unrelated to the
    # feature; polling for up to a generous ceiling below is robust
    # regardless of how slow (or fast) the real round trip is.
    monkeypatch.setattr(settings, "JWT_KEY_CACHE_REFRESH_SECONDS", 1)

    from api.main import app, lifespan

    async with lifespan(app):
        session_factory = async_sessionmaker(bind=pg_engine, expire_on_commit=False)
        async with session_factory() as session:
            session.add(JWTSigningKey(secret=encrypt_secret("picked-up-by-the-background-poller"), is_active=True))
            await session.commit()

        deadline = asyncio.get_event_loop().time() + 20
        while jwt_module._key_cache["active_secret"] != "picked-up-by-the-background-poller":
            if asyncio.get_event_loop().time() > deadline:
                pytest.fail("the background poll loop never picked up the new key within 20s")
            await asyncio.sleep(0.5)

    assert jwt_module._key_cache["active_secret"] == "picked-up-by-the-background-poller"

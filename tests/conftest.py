"""
Shared fixtures for tests/test_auth_*.py. Runs against an in-memory
SQLite DB (via aiosqlite) rather than a real Postgres -- fast, zero setup,
and every column type used in api/models/ (Uuid, Enum, DateTime) is
portable across both backends. What this deliberately does NOT cover:
Postgres-specific behavior (e.g. the exact CASCADE semantics, concurrent
transaction isolation) -- that's what running the real Alembic migration
against a real Postgres in CI/staging is for, not unit tests.
"""

import sys
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from api.config import settings
from api.database import Base, get_db
from api.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
def _disable_rate_limiting_by_default(monkeypatch):
    """
    Applies to every test in tests/ (conftest.py fixtures at this level
    are project-wide, autouse or not) -- rate limiting is OFF by default
    so the fast SQLite suite (which calls /auth/register, /auth/login,
    etc. dozens of times across many tests) doesn't need Redis and can't
    be accidentally rate-limited by its own repeated calls, and so the
    other integration test files aren't rate-limited against each other
    either since they share one real Redis instance across a whole
    `pytest` run. tests/test_rate_limiting_integration.py explicitly
    re-enables it (monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True))
    for the handful of tests that actually verify enforcement.
    """
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)


@pytest.fixture(autouse=True)
def _stub_out_the_hibp_breach_check_by_default(monkeypatch):
    """
    api/security/password_strength.py's is_password_known_breached makes
    a real network call to a third-party API -- every test in tests/
    that registers/resets/sets/changes a password would otherwise depend
    on that API being reachable, making the fast SQLite suite no longer
    fast or network-independent (the exact thing the module docstring
    above this one warns about). Stubbed to "never breached" by default,
    same pattern as rate limiting above; tests that specifically verify
    the rejection path monkeypatch it back to True for themselves.

    Patched on each ROUTER module's own imported name, not on
    api.security.password_strength itself -- `from ... import
    is_password_known_breached` binds a local name in auth.py/password.py/
    account.py at import time, so patching the source module's attribute
    would silently miss all three call sites.
    """
    for module in ("api.routers.auth", "api.routers.password", "api.routers.account"):
        monkeypatch.setattr(f"{module}.is_password_known_breached", _fake_not_breached)


async def _fake_not_breached(password: str) -> bool:
    return False


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    session_factory = async_sessionmaker(bind=db_engine, expire_on_commit=False, autoflush=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session):
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def register_payload():
    return {
        "email": "ada@example.com",
        "password": "correct-horse-battery-staple",
        "full_name": "Ada Lovelace",
        "accept_terms": True,
    }

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


@pytest.fixture(autouse=True)
def _stub_out_domain_verification_scheduling_by_default(monkeypatch):
    """
    Partie 1.4.4's api/security/custom_domains.py's add_custom_domain
    calls schedule_domain_verification, which dispatches a real Celery
    task via apply_async -- a real network round-trip to
    CELERY_BROKER_URL (Redis). Every test in tests/ that adds a custom
    domain (most of tests/test_custom_domains.py and
    tests/test_domain_verification.py) would otherwise depend on Redis
    being reachable, and even when it isn't, apply_async's own
    connection-timeout/retry behavior is far too slow for the fast
    SQLite suite -- same "no real network call belongs in the fast
    suite" reasoning as _stub_out_the_hibp_breach_check_by_default
    above. schedule_domain_verification's own real behavior (including
    its broker-failure best-effort handling) is verified directly in
    tests/test_domain_verification.py, which monkeypatches it back for
    itself where it actually matters to the test.
    """
    monkeypatch.setattr("api.security.custom_domains.schedule_domain_verification", lambda domain, countdown_seconds=None: None)


@pytest.fixture(autouse=True)
def _stub_out_document_processing_scheduling_by_default(monkeypatch):
    """
    Partie 2.1.1's api/security/documents.py's upload_document calls
    schedule_document_processing, which dispatches a real Celery task --
    same real-network-round-trip problem 1.4.4's own
    _stub_out_domain_verification_scheduling_by_default above already
    hit and fixed for schedule_domain_verification (a lesson applied
    here from the start rather than re-learned): every test that
    uploads a document would otherwise depend on Redis and pay
    apply_async's slow connection-timeout/retry cost even when it's
    unreachable. schedule_document_processing's own real behavior is
    verified directly in tests/test_documents.py, which monkeypatches
    it back for itself where it actually matters to the test.
    """
    monkeypatch.setattr("api.security.documents.schedule_document_processing", lambda document_id: None)


@pytest.fixture(autouse=True)
def _stub_out_url_import_scheduling_by_default(monkeypatch):
    """Partie 2.1.10's own equivalent of the fixture above --
    import_document_from_url calls schedule_url_import, the SAME real
    Celery-dispatch problem for the SAME reason. Verified directly in
    tests/test_documents.py, which monkeypatches it back for itself."""
    monkeypatch.setattr("api.security.documents.schedule_url_import", lambda document_id: None)


@pytest.fixture(autouse=True)
def _stub_out_sitemap_import_scheduling_by_default(monkeypatch):
    """Partie 2.1.11's own equivalent of the fixture above --
    start_sitemap_import calls schedule_sitemap_import, the SAME real
    Celery-dispatch problem for the SAME reason. Verified directly in
    tests/test_documents.py, which monkeypatches it back for itself."""
    monkeypatch.setattr(
        "api.security.documents.schedule_sitemap_import",
        lambda sitemap_url, organization_id, workspace_id, filters, max_urls, created_by: None,
    )


@pytest.fixture(autouse=True)
def _stub_out_github_repo_import_scheduling_by_default(monkeypatch):
    """Partie 2.1.12's own equivalent of the fixture above --
    start_github_repo_import calls schedule_github_repo_import, the SAME
    real Celery-dispatch problem for the SAME reason. Verified directly
    in tests/test_documents.py, which monkeypatches it back for itself."""
    monkeypatch.setattr(
        "api.security.documents.schedule_github_repo_import",
        lambda repo_url, organization_id, workspace_id, file_patterns, max_files, created_by: None,
    )


@pytest.fixture(autouse=True)
def _stub_out_github_issues_import_scheduling_by_default(monkeypatch):
    """Partie 2.1.13's own equivalent of the fixture above --
    start_github_issues_import calls schedule_github_issues_import, the
    SAME real Celery-dispatch problem for the SAME reason. Verified
    directly in tests/test_documents.py, which monkeypatches it back
    for itself."""
    monkeypatch.setattr(
        "api.security.documents.schedule_github_issues_import",
        lambda repo_url, organization_id, workspace_id, state, since, labels, max_issues, created_by: None,
    )


@pytest.fixture(autouse=True)
def _stub_out_google_drive_import_scheduling_by_default(monkeypatch):
    """Partie 2.1.14's own equivalent of the fixture above --
    start_google_drive_import calls schedule_google_drive_import, the
    SAME real Celery-dispatch problem for the SAME reason. Verified
    directly in tests/test_documents.py, which monkeypatches it back
    for itself."""
    monkeypatch.setattr(
        "api.security.documents.schedule_google_drive_import",
        lambda drive_id, organization_id, workspace_id, patterns, max_files, created_by: None,
    )


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

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

from api.database import Base, get_db
from api.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


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

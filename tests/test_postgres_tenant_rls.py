"""Tenant RLS on a DISPOSABLE PostgreSQL only (guard: tests/disposable_pg_guard.py -- local host, marked database name,
RAG_DISPOSABLE_PG_CONFIRM, not the application's DATABASE_URL; otherwise the module is skipped with the reason).

Proves what SQLite cannot: with the policy of migration 0137 and a plain (non-owner, non-bypass) role, a transaction sees and writes
ONLY the organization it declared (api/db_tenant_context.py), nothing when it declared none, the declaration survives a commit, a
superuser is unaffected (production behaviour unchanged), and removing the policy makes the cross-tenant read succeed -- i.e. these
assertions really fail when the isolation is missing. Everything lives in a throw-away schema and role, dropped at the end."""

import importlib.util
import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.config import settings
from api.db_tenant_context import bind_tenant
from disposable_pg_guard import disposable_pg_refusal

URL = os.environ.get("RAG_DISPOSABLE_PG_URL", "")
_REFUSAL = disposable_pg_refusal(URL, os.environ.get("RAG_DISPOSABLE_PG_CONFIRM"), str(settings.DATABASE_URL), os.environ.get("DATABASE_URL"))
pytestmark = pytest.mark.skipif(_REFUSAL is not None, reason=f"PostgreSQL tests not authorized: {_REFUSAL}")

_path = Path(__file__).resolve().parent.parent / "api" / "alembic" / "versions" / "0137_tenant_rls_policies_pilot.py"
_spec = importlib.util.spec_from_file_location("migration_0137", _path)
migration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migration)

ORG_A, ORG_B = uuid.uuid4(), uuid.uuid4()
TABLES = ("documents", "credit_transactions")


@pytest.fixture
async def world():
    tag = uuid.uuid4().hex[:8]
    schema, role = f"rls_probe_{tag}", f"rls_probe_role_{tag}"
    engine = create_async_engine(URL)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        await conn.execute(text(f"CREATE ROLE {role} NOLOGIN"))
        for table in TABLES:
            await conn.execute(text(f'CREATE TABLE "{schema}"."{table}" (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), organization_id uuid NOT NULL, payload text)'))
            for org, label in ((ORG_A, "a"), (ORG_B, "b")):
                await conn.execute(text(f'INSERT INTO "{schema}"."{table}" (organization_id, payload) VALUES (:o, :p)'), {"o": org, "p": f"{label}-secret"})
        for statement in migration.create_policy_statements(TABLES, schema):
            await conn.execute(text(statement))
        await conn.execute(text(f'GRANT USAGE ON SCHEMA "{schema}" TO {role}'))
        await conn.execute(text(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA "{schema}" TO {role}'))
    try:
        yield maker, schema, role
    finally:
        async with engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await conn.execute(text(f"DROP ROLE {role}"))
        await engine.dispose()


async def _as_role(session: AsyncSession, role: str):
    await session.execute(text(f"SET LOCAL ROLE {role}"))


async def _payloads(session: AsyncSession, schema: str, table: str = "documents") -> list[str]:
    return sorted((await session.execute(text(f'SELECT payload FROM "{schema}"."{table}"'))).scalars().all())


async def test_a_plain_role_sees_only_the_declared_organization(world):
    maker, schema, role = world
    async with maker() as session:
        await bind_tenant(session, ORG_A)
        await _as_role(session, role)
        assert await _payloads(session, schema) == ["a-secret"]
        assert await _payloads(session, schema, "credit_transactions") == ["a-secret"]


async def test_without_a_declared_organization_nothing_is_visible_or_writable(world):
    maker, schema, role = world
    async with maker() as session:
        await _as_role(session, role)
        assert await _payloads(session, schema) == []
        with pytest.raises(DBAPIError, match="row-level security"):
            await session.execute(text(f'INSERT INTO "{schema}"."documents" (organization_id, payload) VALUES (:o, \'x\')'), {"o": ORG_A})


async def test_a_tenant_cannot_write_into_or_modify_another_tenant(world):
    maker, schema, role = world
    async with maker() as session:
        await bind_tenant(session, ORG_A)
        await _as_role(session, role)
        updated = await session.execute(text(f'UPDATE "{schema}"."documents" SET payload = \'hacked\' WHERE organization_id = :o'), {"o": ORG_B})
        assert updated.rowcount == 0
        deleted = await session.execute(text(f'DELETE FROM "{schema}"."documents" WHERE organization_id = :o'), {"o": ORG_B})
        assert deleted.rowcount == 0
        with pytest.raises(DBAPIError, match="row-level security"):
            await session.execute(text(f'INSERT INTO "{schema}"."documents" (organization_id, payload) VALUES (:o, \'planted\')'), {"o": ORG_B})
    async with maker() as admin:
        assert await _payloads(admin, schema) == ["a-secret", "b-secret"]  # the other tenant's data is intact


async def test_the_declaration_survives_a_commit(world):
    maker, schema, role = world
    async with maker() as session:
        await bind_tenant(session, ORG_A)
        await _as_role(session, role)
        assert await _payloads(session, schema) == ["a-secret"]
        await session.commit()
        await _as_role(session, role)  # a NEW transaction: the listener re-applied the organization, nobody called bind_tenant again
        assert await _payloads(session, schema) == ["a-secret"]


async def test_the_declaration_never_leaks_to_the_next_session_on_the_same_pooled_connection(world):
    maker, schema, role = world
    async with maker() as first:
        await bind_tenant(first, ORG_A)
        await first.commit()
    async with maker() as second:  # same pool, no declaration
        await _as_role(second, role)
        assert await _payloads(second, schema) == []


async def test_a_superuser_is_unaffected_which_is_todays_production_behaviour(world):
    maker, schema, _role = world
    async with maker() as session:
        assert await _payloads(session, schema) == ["a-secret", "b-secret"]


async def test_the_isolation_assertions_fail_when_the_isolation_is_missing(world):
    """Mutation proof: with a permissive policy (the shape of a forgotten filter) a plain role reads BOTH tenants, so the tests above are
    not vacuous. And with RLS enabled but NO policy -- today's state of every table -- a plain role sees nothing at all (default deny)."""
    maker, schema, role = world
    async with maker() as session:
        for statement in migration.drop_policy_statements(TABLES, schema):
            await session.execute(text(statement))
        await session.commit()
        await bind_tenant(session, ORG_A)
        await _as_role(session, role)
        assert await _payloads(session, schema) == []  # no policy: default deny (and an owner/bypass role would see everything)
        await session.rollback()
        await session.execute(text(f'CREATE POLICY permissive ON "{schema}"."documents" USING (true)'))
        await session.commit()
        await bind_tenant(session, ORG_A)
        await _as_role(session, role)
        assert await _payloads(session, schema) == ["a-secret", "b-secret"]  # the leak the real policy closes


async def test_the_policy_statements_are_idempotent(world):
    maker, schema, _role = world
    async with maker() as session:
        for _ in range(2):
            for statement in migration.create_policy_statements(TABLES, schema):
                await session.execute(text(statement))
        count = await session.scalar(text("SELECT count(*) FROM pg_policies WHERE schemaname = :s"), {"s": schema})
        assert count == len(TABLES)

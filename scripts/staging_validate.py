"""Staging-only catalog checks, migration runner and restricted-role RLS setup."""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import socket
import subprocess
import sys
from urllib.parse import quote

from asyncpg import PostgresError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

if __package__:
    from .staging_target import (
        ROOT,
        StagingTargetError,
        isolated_environment,
        staging_url,
    )
else:
    from staging_target import (
        ROOT,
        StagingTargetError,
        isolated_environment,
        staging_url,
    )

CATALOG_QUERIES = {
    "identity": "SELECT version(), current_database(), current_user",
    "tenant_role": """
        SELECT rolname, rolcanlogin, rolsuper, rolbypassrls, rolcreatedb, rolcreaterole
        FROM pg_roles WHERE rolname = 'rag_staging_tenant'
    """,
    "tenant_role_memberships": """
        SELECT granted.rolname AS granted_role, member.rolname AS member_role,
        m.admin_option, m.inherit_option, m.set_option
        FROM pg_auth_members m JOIN pg_roles granted ON granted.oid = m.roleid
        JOIN pg_roles member ON member.oid = m.member
        WHERE 'rag_staging_tenant' IN (granted.rolname, member.rolname)
    """,
    "tables": "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename",
    "vector": "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector'",
    "table_count": "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public'",
    "workspace_description": """
        SELECT column_name, data_type, is_nullable FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'workspaces' AND column_name = 'description'
    """,
    "embedding_columns": """
        SELECT column_name, data_type, udt_name FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'document_chunks'
        AND column_name LIKE '%embedding%'
    """,
    "chunk_indexes": """
        SELECT indexname, indexdef FROM pg_indexes
        WHERE schemaname = 'public' AND tablename = 'document_chunks'
    """,
    "constraints": """
        SELECT contype, COUNT(*) FROM pg_constraint
        WHERE connamespace = 'public'::regnamespace GROUP BY contype ORDER BY contype
    """,
    "policies": """
        SELECT tablename, policyname, roles, cmd, qual, with_check
        FROM pg_policies WHERE schemaname = 'public' ORDER BY tablename, policyname
    """,
    "rls": """
        SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class
        WHERE relnamespace = 'public'::regnamespace AND relkind IN ('r', 'p') ORDER BY relname
    """,
}
EXCLUDED_TABLES = {
    "audit_logs", "document_audit_logs", "jwt_signing_keys",
    "permissions", "plans", "billing_plans",
}

def validate_tenant_role(flags: dict[str, bool], unsafe_memberships: bool, owns_tables: bool) -> None:
    if any(flags.values()) or unsafe_memberships or owns_tables:
        raise StagingTargetError(
            "Staging tenant role must be NOLOGIN, unprivileged, without untrusted memberships "
            "and must not own public tables; refused."
        )


async def catalog(action: str) -> None:
    url = staging_url()
    engine = create_async_engine(url, poolclass=NullPool, connect_args={
        "timeout": 10, "ssl": "require",
        "server_settings": {"application_name": "rag_staging_validation", "statement_timeout": "30000"},
    })
    try:
        async with engine.begin() as conn:
            if action == "inspect":
                await conn.execute(text("SET TRANSACTION READ ONLY"))
            if action == "vector":
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                print("CREATE EXTENSION vector: completed on allowlisted staging.")
            if action == "policies":
                await conn.execute(text("""
                    DO $role$
                    BEGIN
                        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rag_staging_tenant') THEN
                            CREATE ROLE rag_staging_tenant NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
                        END IF;
                    END $role$
                """))
                role = (await conn.execute(text("""
                    SELECT rolcanlogin, rolsuper, rolbypassrls, rolcreatedb, rolcreaterole
                    FROM pg_roles WHERE rolname = 'rag_staging_tenant'
                """))).mappings().one()
                memberships = (await conn.execute(text("""
                    SELECT EXISTS (
                        SELECT 1 FROM pg_auth_members m
                        JOIN pg_roles granted ON granted.oid = m.roleid
                        JOIN pg_roles member ON member.oid = m.member
                        WHERE member.rolname = 'rag_staging_tenant'
                        OR (
                            granted.rolname = 'rag_staging_tenant'
                            AND NOT (
                                member.rolname = current_user
                                AND (member.rolsuper OR member.rolbypassrls)
                            )
                        )
                    )
                """))).scalar_one()
                owns_tables = (await conn.execute(text("""
                    SELECT EXISTS (
                        SELECT 1 FROM pg_class c JOIN pg_roles r ON r.oid = c.relowner
                        WHERE r.rolname = 'rag_staging_tenant'
                        AND c.relnamespace = 'public'::regnamespace AND c.relkind IN ('r', 'p')
                    )
                """))).scalar_one()
                validate_tenant_role(dict(role), memberships, owns_tables)
                administrator = (await conn.execute(text("""
                    SELECT rolname, rolsuper, rolbypassrls
                    FROM pg_roles WHERE rolname = current_user
                """))).mappings().one()
                if not (administrator["rolsuper"] or administrator["rolbypassrls"]):
                    raise StagingTargetError("RLS validation requires a trusted bypass administrator; refused.")
                administrator_name = conn.dialect.identifier_preparer.quote(administrator["rolname"])
                await conn.execute(text(
                    "GRANT rag_staging_tenant TO " + administrator_name +
                    " WITH INHERIT FALSE, SET TRUE"
                ))
                await conn.execute(text("GRANT USAGE ON SCHEMA public TO rag_staging_tenant"))
                tables = (await conn.execute(text("""
                    SELECT c.table_name FROM information_schema.columns c
                    JOIN information_schema.tables t
                    ON t.table_schema = c.table_schema AND t.table_name = c.table_name
                    WHERE c.table_schema = 'public' AND c.column_name = 'organization_id'
                    AND c.udt_name = 'uuid' AND t.table_type = 'BASE TABLE'
                    ORDER BY c.table_name
                """))).scalars().all()
                if not tables:
                    raise StagingTargetError("No direct tenant UUID tables found; migrate staging first.")
                quote = conn.dialect.identifier_preparer.quote
                for table in tables:
                    if table in EXCLUDED_TABLES:
                        continue
                    name = f"public.{quote(table)}"
                    policy = quote(f"{table}_tenant_isolation")
                    await conn.execute(text("ALTER TABLE " + name + " ENABLE ROW LEVEL SECURITY"))
                    await conn.execute(text("GRANT SELECT, INSERT, UPDATE, DELETE ON " + name + " TO rag_staging_tenant"))
                    await conn.execute(text("DROP POLICY IF EXISTS " + policy + " ON " + name))
                    condition = "organization_id = NULLIF(current_setting('app.current_organization_id', true), '')::uuid"
                    await conn.execute(text(
                        "CREATE POLICY " + policy + " ON " + name + " TO rag_staging_tenant "
                        "USING (" + condition + ") WITH CHECK (" + condition + ")"
                    ))
                    print(f"POLICY prepared: {table} (restricted staging role only)")
            for name, query in CATALOG_QUERIES.items():
                rows = (await conn.execute(text(query))).mappings().all()
                print(f"{name}: {[dict(row) for row in rows]}")
    finally:
        await engine.dispose()


def run_process(arguments: list[str], env: dict[str, str], password: str) -> int:
    result = subprocess.run(
        arguments, cwd=ROOT, env=env, capture_output=True, text=True, check=False,
    )
    combined = result.stdout + result.stderr
    for value in (password, quote(password, safe=""), quote(password, safe="+")):
        combined = combined.replace(value, "[REDACTED]")
    for key, value in env.items():
        if value and key in {
            "JWT_SECRET_KEY", "SESSION_MIDDLEWARE_SECRET", "AUDIT_LOG_HMAC_SECRET_KEY",
            "SECRET_ENCRYPTION_KEY", "ENCRYPTION_MASTER_KEY", "PGPASSWORD",
        }:
            combined = combined.replace(value, "[REDACTED]")
    print(combined, end="")
    return result.returncode


def alembic(action: str) -> int:
    url = staging_url()
    env = isolated_environment(url)
    os.environ.clear()
    os.environ.update(env)
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "api" / "alembic"))
    heads = ScriptDirectory.from_config(config).get_heads()
    if heads != ["0132"]:
        raise StagingTargetError("Unexpected local migration head; expected only 0132.")
    args = ["current"] if action == "current" else ["upgrade", "head"]
    return run_process(
        [sys.executable, "-m", "alembic", "-c", str(ROOT / "alembic.ini"), *args],
        env, url.password,
    )


def tests(idor_only: bool = False, postgres_integration: bool = False, expect_policies: bool = True) -> int:
    url = staging_url()
    env = isolated_environment(url)
    env["RAG_STAGING_TESTS"] = "YES"
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    if expect_policies:
        env["RAG_EXPECT_STAGING_RLS_POLICIES"] = "1"
    else:
        env.pop("RAG_EXPECT_STAGING_RLS_POLICIES", None)
    for suffix in ("A", "B"):
        for kind in ("USER", "ORG"):
            key = f"RAG_STAGING_{kind}_{suffix}"
            if key in os.environ:
                env[key] = os.environ[key]
    if postgres_integration:
        files = ["tests/test_postgres_integration.py"]
    else:
        files = ["tests/test_staging_full_idor.py"]
        if not idor_only:
            files.insert(0, "tests/test_staging_idor.py")
    folder = ROOT / "staging-artifacts"
    folder.mkdir(exist_ok=True)
    report = folder / ("idor-browser-tenants.xml" if idor_only else "staging-tests.xml")
    return run_process(
        [sys.executable, "-m", "pytest", "-p", "pytest_asyncio.plugin",
         *files, "-q", "--tb=short", f"--junitxml={report}"],
        env, url.password,
    )


def backup() -> int:
    executable = shutil.which("pg_dump")
    if not executable:
        raise StagingTargetError("pg_dump is not installed; no backup was attempted.")
    url = staging_url()
    env = isolated_environment(url)
    env.update({"PGPASSWORD": url.password, "PGSSLMODE": "require", "PGCONNECT_TIMEOUT": "10"})
    folder = ROOT / "staging-artifacts"
    folder.mkdir(exist_ok=True)
    destination = folder / "staging_backup.sql"
    if destination.exists():
        raise StagingTargetError("Existing staging backup will not be overwritten.")
    result = run_process(
        [executable, "--host", url.host, "--port", str(url.port), "--username", url.username,
         "--dbname", "postgres", "--no-password", "--file", str(destination)],
        env, url.password,
    )
    if result == 0:
        print(f"Backup complete: {destination.name}, bytes={destination.stat().st_size}")
    else:
        print("Backup FAILED: any output file is incomplete and must not be used for restore.")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("dns", "inspect", "current", "vector", "upgrade", "policies", "tests", "backup"))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--idor-only", action="store_true", help="Run nine representative resource checks, not the separate RLS policy check.")
    parser.add_argument("--postgres-integration", action="store_true", help="Run only PostgreSQL integration tests against the allowlisted staging database.")
    parser.add_argument("--without-staging-policy-expectation", action="store_true", help="Omit the staging-policy expectation for an explicit default-profile check.")
    args = parser.parse_args()
    if args.action == "dns":
        try:
            target = staging_url()
            addresses = socket.getaddrinfo(target.host, target.port, type=socket.SOCK_STREAM)
        except StagingTargetError as exc:
            print(f"BLOCKED: {exc}", file=sys.stderr)
            return 2
        except socket.gaierror as exc:
            print(f"BLOCKED_EXTERNAL: staging DNS unresolved (error {exc.errno}); no DB contacted.")
            return 2
        print(f"Staging DNS addresses: {sorted({item[4][0] for item in addresses})}")
        return 0
    if not args.execute:
        print("DRY RUN: no connection, migration, policy or extension change.")
        return 0
    try:
        if args.action in {"current", "upgrade"}:
            return alembic(args.action)
        if args.action == "tests":
            if args.postgres_integration and args.idor_only:
                raise StagingTargetError("--postgres-integration and --idor-only cannot be combined.")
            return tests(args.idor_only, args.postgres_integration, not args.without_staging_policy_expectation)
        if args.action == "backup":
            return backup()
        asyncio.run(catalog(args.action))
    except StagingTargetError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    except (OSError, SQLAlchemyError, PostgresError, TimeoutError) as exc:
        print(f"FAIL: staging action raised {type(exc).__name__}; details withheld to protect credentials.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Read-only PostgreSQL catalog audit; requires explicit environment approval."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

QUERIES = {
    "identity": """
        SELECT current_database() AS database_name,
               current_user AS current_user,
               current_setting('server_version') AS server_version,
               current_setting('transaction_read_only') AS transaction_read_only,
               role.rolsuper AS is_superuser,
               role.rolbypassrls AS bypasses_rls
        FROM pg_roles AS role
        WHERE role.rolname = current_user
    """,
    "rls_tables": """
        SELECT n.nspname AS schema_name,
               c.relname AS table_name,
               c.relrowsecurity AS rls_enabled,
               c.relforcerowsecurity AS force_rls,
               pg_get_userbyid(c.relowner) AS owner_name
        FROM pg_class AS c
        JOIN pg_namespace AS n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
        ORDER BY c.relname
    """,
    "policies": """
        SELECT schemaname, tablename, policyname, roles, cmd
        FROM pg_policies
        WHERE schemaname = 'public'
        ORDER BY tablename, policyname
    """,
    "vector_extension": """
        SELECT extname, extversion
        FROM pg_extension
        WHERE extname = 'vector'
    """,
    "alembic_revision": """
        SELECT to_regclass('public.alembic_version') IS NOT NULL AS table_exists
    """,
    "public_table_grants": """
        SELECT table_name, privilege_type
        FROM information_schema.table_privileges
        WHERE table_schema = 'public' AND grantee = current_user
        ORDER BY table_name, privilege_type
    """,
}


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Connect and run fixed catalog SELECTs (otherwise only describe the plan).",
    )
    parser.add_argument(
        "--environment",
        choices=("DEV", "TEST", "STAGING"),
        help="Explicitly identified non-production target; required with --execute.",
    )
    return parser.parse_args()


def _database_url() -> str:
    value = os.environ.get("POSTGRES_READONLY_AUDIT_URL")
    if not value:
        raise RuntimeError("POSTGRES_READONLY_AUDIT_URL is required; the URL is never printed.")
    url = make_url(value)
    if url.get_backend_name() not in {"postgres", "postgresql"}:
        raise RuntimeError("Only a PostgreSQL URL is accepted.")
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+asyncpg")
    if url.drivername != "postgresql+asyncpg":
        raise RuntimeError("Use the asyncpg PostgreSQL driver.")
    return url.render_as_string(hide_password=False)


async def _run() -> None:
    args = _arguments()
    if not args.execute:
        print("DRY RUN: no database connection; fixed catalog SELECTs are prepared.")
        return
    if args.environment is None:
        raise RuntimeError("--environment DEV, TEST, or STAGING is required.")
    if os.environ.get("RAG_POSTGRES_READONLY_AUDIT_APPROVED") != "YES":
        raise RuntimeError("Set RAG_POSTGRES_READONLY_AUDIT_APPROVED=YES after target review.")

    url = _database_url()
    engine = create_async_engine(
        url,
        poolclass=NullPool,
        connect_args={
            "server_settings": {
                "application_name": "rag_saas_readonly_catalog_audit",
                "default_transaction_read_only": "on",
                "lock_timeout": "1000",
                "statement_timeout": "10000",
            }
        },
    )
    try:
        async with engine.begin() as connection:
            await connection.execute(text("SET TRANSACTION READ ONLY"))
            for name, statement in QUERIES.items():
                result = await connection.execute(text(statement))
                rows = [dict(row) for row in result.mappings()]
                print(f"{name}: {rows}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(_run())
    except (RuntimeError, OSError) as exc:
        print(f"Audit not run: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

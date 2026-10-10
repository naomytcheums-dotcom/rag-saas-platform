"""Tenant row level security policies, PILOT (Lot A) -- additive, idempotent, reversible.

Context: RLS has been ENABLED on every table since 0002/0098/0131, but no policy was ever created and the application connects with a
role that bypasses RLS, so RLS protected nothing. This migration adds the policy that makes RLS meaningful on a first set of
data-heavy tables; the remaining tables follow in later migrations, table by table (audit-reports/remediation-2026-10-10/03-tenant-isolation.*).

  USING / WITH CHECK:  organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid

* A row is visible, insertable and updatable only when the transaction declared its organization (api/db_tenant_context.py). Without
  a declared organization the comparison is NULL: nothing is visible and nothing can be written (fail closed).
* The policy is INERT for superusers, BYPASSRLS roles and the table owner (FORCE ROW LEVEL SECURITY is deliberately NOT set): the
  current production behaviour is unchanged. It only starts to protect when the runtime role is switched to a plain, non-owner role.
* Nothing is dropped or rewritten; downgrade drops exactly the policies created here. Existing migrations are untouched.

Revision ID: 0137
Revises: 0136
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0137"
down_revision: str | None = "0136"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

POLICY_NAME = "tenant_isolation"
PILOT_TABLES: tuple[str, ...] = ("documents", "document_chunks", "credits", "credit_transactions", "invoices", "evaluation_datasets")
_PREDICATE = "organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid"


def create_policy_statements(tables: Sequence[str], schema: str | None = None) -> list[str]:
    """Idempotent statements (safe to run twice). `schema` qualifies the tables (used by the PostgreSQL tests)."""
    statements = []
    for table in tables:
        qualified = f'"{schema}"."{table}"' if schema else f'"{table}"'
        statements += [
            f"ALTER TABLE {qualified} ENABLE ROW LEVEL SECURITY",
            f"DROP POLICY IF EXISTS {POLICY_NAME} ON {qualified}",
            f"CREATE POLICY {POLICY_NAME} ON {qualified} USING ({_PREDICATE}) WITH CHECK ({_PREDICATE})",
        ]
    return statements


def drop_policy_statements(tables: Sequence[str], schema: str | None = None) -> list[str]:
    statements = []
    for table in tables:
        qualified = f'"{schema}"."{table}"' if schema else f'"{table}"'
        statements.append(f"DROP POLICY IF EXISTS {POLICY_NAME} ON {qualified}")
    return statements


def upgrade() -> None:
    for statement in create_policy_statements(PILOT_TABLES):
        op.execute(statement)


def downgrade() -> None:
    for statement in drop_policy_statements(PILOT_TABLES):
        op.execute(statement)

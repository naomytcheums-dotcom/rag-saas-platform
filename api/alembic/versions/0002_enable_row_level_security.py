"""enable row level security on all public tables

Supabase's own Advisor flags every table with RLS disabled as a critical
finding, because its PostgREST/Data API layer -- if ever turned on, even
by accident later -- respects RLS and would otherwise expose these tables
to anyone holding an anon/authenticated key. This app's own backend
connects with the `postgres` role (a superuser-equivalent that bypasses
RLS by default in Postgres/Supabase), so enabling RLS here with zero
policies is pure defense-in-depth: it changes nothing for this app's own
reads/writes, and turns "wide open" into "deny all" for any other access
path. No policies are added because nothing but this app's own backend
role should ever query these tables directly.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-01
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ["users", "oauth_accounts", "sessions", "password_reset_tokens", "email_verification_tokens"]


def upgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY")

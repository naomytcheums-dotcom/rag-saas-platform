"""add casbin_rule (Etape 1.2.7 -- RBAC policy engine)

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Schema dictated by casbin_async_sqlalchemy_adapter.CasbinRule, not
    designed freely -- the adapter's own generated SQL (id/ptype/v0..v5,
    all String(255)) must match exactly, or its queries against this
    table fail. Created here (not via the adapter's own
    Base.metadata.create_all(), which it never calls itself) so this
    table follows the same "every table has an explicit migration"
    convention as everything else in api/alembic/versions/.
    """
    op.create_table(
        "casbin_rule",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ptype", sa.String(255), nullable=True),
        sa.Column("v0", sa.String(255), nullable=True),
        sa.Column("v1", sa.String(255), nullable=True),
        sa.Column("v2", sa.String(255), nullable=True),
        sa.Column("v3", sa.String(255), nullable=True),
        sa.Column("v4", sa.String(255), nullable=True),
        sa.Column("v5", sa.String(255), nullable=True),
    )
    # Every real enforce() call filters by (ptype, v0, v1, v2) at minimum
    # (subject, domain, object -- see api/security/rbac.py); this index
    # only matters for admin/debug queries and ad-hoc policy lookups, not
    # enforce() itself, which works entirely off the in-memory policy set
    # loaded at startup (api/security/rbac.py's module docstring).
    op.create_index("ix_casbin_rule_ptype_v0_v1", "casbin_rule", ["ptype", "v0", "v1"])
    op.execute("ALTER TABLE public.casbin_rule ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("casbin_rule")

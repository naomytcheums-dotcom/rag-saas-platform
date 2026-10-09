"""Tenant ownership of Twilio call records (SEC-004).

Additive and reversible: a nullable organization_id (rows recorded before this revision stay NULL and are visible to platform
superadmins only) with an index for the per-organization history.

Revision ID: 0135
Revises: 0133
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0135"
down_revision: str | None = "0133"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("call_records", sa.Column("organization_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_call_records_organization_id", "call_records", "organizations", ["organization_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("ix_call_records_organization_id", "call_records", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_call_records_organization_id", table_name="call_records")
    op.drop_constraint("fk_call_records_organization_id", "call_records", type_="foreignkey")
    op.drop_column("call_records", "organization_id")

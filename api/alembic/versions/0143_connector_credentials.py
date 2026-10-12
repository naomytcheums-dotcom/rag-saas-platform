"""Per-organization connector credentials (docs/DECISIONS.md D17). Additive and reversible; row level security enabled like every table since 0131.

Revision ID: 0143
Revises: 0142
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0143"
down_revision: str | None = "0142"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connector_credentials",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("encrypted_payload", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "provider", name="uq_connector_credentials_org_provider"),
    )
    op.create_index("ix_connector_credentials_organization_id", "connector_credentials", ["organization_id"])
    op.execute("ALTER TABLE connector_credentials ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("connector_credentials")

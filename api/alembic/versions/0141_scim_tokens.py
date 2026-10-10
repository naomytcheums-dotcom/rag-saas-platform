"""SCIM 2.0 provisioning tokens (spec 10.4.3). Additive and reversible; row level security enabled like every table since 0131.

Revision ID: 0141
Revises: 0140
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0141"
down_revision: str | None = "0140"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scim_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_scim_tokens_organization_id", "scim_tokens", ["organization_id"])
    op.create_index("ix_scim_tokens_token_hash", "scim_tokens", ["token_hash"], unique=True)
    op.execute("ALTER TABLE scim_tokens ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("scim_tokens")

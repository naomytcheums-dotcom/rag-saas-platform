"""AI credits pack (monthly included credits per plan) + BYOK (per-org
LLM provider API key, encrypted at rest).

Revision ID: 0109
Revises: 0108
Create Date: 2026-09-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0109"
down_revision: Union[str, None] = "0108"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("plans", sa.Column("monthly_credits_included", sa.Integer(), nullable=True))

    op.create_table(
        "organization_llm_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("encrypted_api_key", sa.String(length=1000), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "provider", name="uq_organization_llm_config_org_provider"),
    )
    op.create_index("ix_organization_llm_configs_organization_id", "organization_llm_configs", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_organization_llm_configs_organization_id", table_name="organization_llm_configs")
    op.drop_table("organization_llm_configs")
    op.drop_column("plans", "monthly_credits_included")

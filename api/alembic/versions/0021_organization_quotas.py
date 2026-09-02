"""add organization_quotas (Partie 1.3.6)

Revision ID: 0021
Revises: 0020
Create Date: 2026-09-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organization_quotas",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("max_users", sa.Integer(), nullable=False),
        sa.Column("max_workspaces", sa.Integer(), nullable=False),
        sa.Column("max_teams", sa.Integer(), nullable=False),
        sa.Column("max_documents", sa.Integer(), nullable=False),
        sa.Column("max_storage_mb", sa.Integer(), nullable=False),
        sa.Column("max_requests_per_month", sa.Integer(), nullable=False),
        sa.Column("max_requests_per_day", sa.Integer(), nullable=False),
        sa.Column("max_api_calls", sa.Integer(), nullable=False),
        sa.Column("max_agents", sa.Integer(), nullable=False),
        sa.Column("max_kb_size_mb", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint("uq_organization_quotas_organization_id", "organization_quotas", ["organization_id"])
    op.execute("ALTER TABLE public.organization_quotas ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("organization_quotas")

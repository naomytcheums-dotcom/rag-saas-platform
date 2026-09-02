"""add organization_usage and organization_usage_details (Partie 1.3.8)

Revision ID: 0023
Revises: 0022
Create Date: 2026-09-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organization_usage",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("metric", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
    )
    op.create_unique_constraint(
        "uq_organization_usage_org_date_metric", "organization_usage", ["organization_id", "date", "metric"],
    )
    op.execute("ALTER TABLE public.organization_usage ENABLE ROW LEVEL SECURITY")

    op.create_table(
        "organization_usage_details",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("metric", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
    )
    op.create_index(
        "ix_organization_usage_details_org_metric_timestamp",
        "organization_usage_details", ["organization_id", "metric", "timestamp"],
    )
    op.execute("ALTER TABLE public.organization_usage_details ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("ix_organization_usage_details_org_metric_timestamp", table_name="organization_usage_details")
    op.drop_table("organization_usage_details")
    op.drop_table("organization_usage")

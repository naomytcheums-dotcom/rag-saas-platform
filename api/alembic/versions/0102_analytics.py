"""Partie 20 -- advanced analytics: analytics_events, analytics_aggregates,
analytics_dashboards. See api/models/analytics.py's own docstring for
why these 3 tables are genuinely new (not a duplicate of AuditLog,
OrganizationUsage, or any existing "dashboard").

Revision ID: 0102
Revises: 0101
Create Date: 2026-09-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0102"
down_revision: Union[str, None] = "0101"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analytics_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("event_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analytics_events_organization_id", "analytics_events", ["organization_id"])
    op.create_index("ix_analytics_events_event_type", "analytics_events", ["event_type"])
    op.create_index("ix_analytics_events_created_at", "analytics_events", ["created_at"])
    op.create_index("ix_analytics_events_org_type_created", "analytics_events", ["organization_id", "event_type", "created_at"])
    op.execute("ALTER TABLE public.analytics_events ENABLE ROW LEVEL SECURITY")

    op.create_table(
        "analytics_aggregates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("metric_name", sa.String(length=100), nullable=False),
        sa.Column("metric_value", sa.Numeric(20, 4), nullable=False),
        sa.Column("period", sa.String(length=10), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analytics_aggregates_organization_id", "analytics_aggregates", ["organization_id"])
    op.create_index(
        "uq_analytics_aggregates_identity", "analytics_aggregates",
        ["organization_id", "metric_name", "period", "period_start"], unique=True,
    )
    op.execute("ALTER TABLE public.analytics_aggregates ENABLE ROW LEVEL SECURITY")

    op.create_table(
        "analytics_dashboards",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("widgets", sa.JSON(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analytics_dashboards_organization_id", "analytics_dashboards", ["organization_id"])
    op.execute("ALTER TABLE public.analytics_dashboards ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("analytics_dashboards")
    op.drop_index("uq_analytics_aggregates_identity", table_name="analytics_aggregates")
    op.drop_table("analytics_aggregates")
    op.drop_table("analytics_events")

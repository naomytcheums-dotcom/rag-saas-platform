"""Partie 11 -- admin dashboard: organization/user suspension fields,
system_logs, plans, subscriptions.

Revision ID: 0089
Revises: 0088
Create Date: 2026-09-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0089"
down_revision: Union[str, None] = "0088"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("is_suspended", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("organizations", sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("organizations", sa.Column("suspended_reason", sa.String(500), nullable=True))

    op.add_column("users", sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("suspended_reason", sa.String(500), nullable=True))

    op.create_table(
        "system_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("level", sa.String(10), nullable=False),
        sa.Column("logger_name", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("module", sa.String(200), nullable=True),
        sa.Column("function", sa.String(200), nullable=True),
        sa.Column("line", sa.Integer(), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_system_logs_level", "system_logs", ["level"])
    op.create_index("ix_system_logs_logger_name", "system_logs", ["logger_name"])
    op.create_index("ix_system_logs_request_id", "system_logs", ["request_id"])
    op.create_index("ix_system_logs_created_at", "system_logs", ["created_at"])

    subscription_status = sa.Enum("active", "canceled", "past_due", "pending", name="subscriptionstatus")

    op.create_table(
        "plans",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("key", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("monthly_price_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_documents", sa.Integer(), nullable=True),
        sa.Column("max_agents", sa.Integer(), nullable=True),
        sa.Column("max_members", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("plan_id", sa.Uuid(), sa.ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", subscription_status, nullable=False, server_default="active"),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("subscriptions")
    op.drop_table("plans")
    sa.Enum(name="subscriptionstatus").drop(op.get_bind(), checkfirst=True)

    op.drop_table("system_logs")

    op.drop_column("users", "suspended_reason")
    op.drop_column("users", "suspended_at")

    op.drop_column("organizations", "suspended_reason")
    op.drop_column("organizations", "suspended_at")
    op.drop_column("organizations", "is_suspended")

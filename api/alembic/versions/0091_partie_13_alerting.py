"""Partie 13.3 -- alert_channels, alert_rules, alert_history, incidents.

Revision ID: 0091
Revises: 0090
Create Date: 2026-09-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0091"
down_revision: Union[str, None] = "0090"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    channel_type = sa.Enum("email", "webhook", name="alertchanneltype")
    operator_type = sa.Enum("gt", "gte", "lt", "lte", name="alertoperator")
    severity_type = sa.Enum("critical", "high", "medium", "low", "info", name="alertseverity")
    incident_status = sa.Enum("open", "investigating", "resolved", name="incidentstatus")

    op.create_table(
        "alert_channels",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("type", channel_type, nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_alert_channels_organization_id", "alert_channels", ["organization_id"])

    op.create_table(
        "alert_rules",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("metric", sa.String(64), nullable=False),
        sa.Column("operator", operator_type, nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("severity", severity_type, nullable=False, server_default="medium"),
        sa.Column("channel_id", sa.Uuid(), sa.ForeignKey("alert_channels.id", ondelete="SET NULL"), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_alert_rules_organization_id", "alert_rules", ["organization_id"])

    op.create_table(
        "alert_history",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("rule_id", sa.Uuid(), sa.ForeignKey("alert_rules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("value_at_trigger", sa.Float(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("notified", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_alert_history_rule_id", "alert_history", ["rule_id"])
    op.create_index("ix_alert_history_triggered_at", "alert_history", ["triggered_at"])

    op.create_table(
        "incidents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity", severity_type, nullable=False, server_default="medium"),
        sa.Column("status", incident_status, nullable=False, server_default="open"),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_incidents_organization_id", "incidents", ["organization_id"])


def downgrade() -> None:
    op.drop_table("incidents")
    sa.Enum(name="incidentstatus").drop(op.get_bind(), checkfirst=True)
    op.drop_table("alert_history")
    op.drop_table("alert_rules")
    sa.Enum(name="alertoperator").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="alertseverity").drop(op.get_bind(), checkfirst=True)
    op.drop_table("alert_channels")
    sa.Enum(name="alertchanneltype").drop(op.get_bind(), checkfirst=True)

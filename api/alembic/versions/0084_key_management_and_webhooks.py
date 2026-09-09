"""extend organization_api_keys (9.2.1/9.2.5/9.2.6) + key_rotation_history (9.2.2) + webhooks (9.2.7)

Revision ID: 0084
Revises: 0083
Create Date: 2026-09-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0084"
down_revision: Union[str, None] = "0083"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("organization_api_keys", sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("organization_api_keys", sa.Column("rate_limit", sa.Integer(), nullable=True))
    op.add_column("organization_api_keys", sa.Column("rate_limit_period", sa.String(20), nullable=True))
    op.add_column("organization_api_keys", sa.Column("quota_limit", sa.Integer(), nullable=True))
    op.add_column("organization_api_keys", sa.Column("quota_period", sa.String(20), nullable=True))
    op.add_column("organization_api_keys", sa.Column("quota_used", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("organization_api_keys", sa.Column("quota_reset_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("organization_api_keys", sa.Column("scheduled_rotation_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "key_rotation_history",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("key_id", sa.Uuid(), sa.ForeignKey("organization_api_keys.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rotated_from", sa.Uuid(), sa.ForeignKey("organization_api_keys.id", ondelete="SET NULL"), nullable=True),
        sa.Column("rotated_to", sa.Uuid(), sa.ForeignKey("organization_api_keys.id", ondelete="SET NULL"), nullable=True),
        sa.Column("rotated_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("rotated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
    )
    op.create_index("ix_key_rotation_history_key_id", "key_rotation_history", ["key_id"])

    op.create_table(
        "webhooks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("events", sa.JSON(), nullable=False),
        sa.Column("headers", sa.JSON(), nullable=True),
        sa.Column("secret", sa.String(200), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("timeout", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_webhooks_organization_id", "webhooks", ["organization_id"])

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("webhook_id", sa.Uuid(), sa.ForeignKey("webhooks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event", sa.String(50), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_webhook_deliveries_webhook_id", "webhook_deliveries", ["webhook_id"])


def downgrade() -> None:
    op.drop_table("webhook_deliveries")
    op.drop_table("webhooks")
    op.drop_table("key_rotation_history")
    op.drop_column("organization_api_keys", "scheduled_rotation_at")
    op.drop_column("organization_api_keys", "quota_reset_at")
    op.drop_column("organization_api_keys", "quota_used")
    op.drop_column("organization_api_keys", "quota_period")
    op.drop_column("organization_api_keys", "quota_limit")
    op.drop_column("organization_api_keys", "rate_limit_period")
    op.drop_column("organization_api_keys", "rate_limit")
    op.drop_column("organization_api_keys", "is_active")

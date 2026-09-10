"""Partie 15 -- integration_connections, integration_mappings,
integration_logs, airbyte_connections.

Revision ID: 0092
Revises: 0091
Create Date: 2026-09-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0092"
down_revision: Union[str, None] = "0091"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    provider_type = sa.Enum("webhook", "zapier", "make", "n8n", name="integrationprovider")
    action_type = sa.Enum("ingest_document", "log_only", name="integrationaction")
    log_status_type = sa.Enum("accepted", "rejected", "error", name="integrationlogstatus")

    op.create_table(
        "integration_connections",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("provider", provider_type, nullable=False, server_default="webhook"),
        sa.Column("action", action_type, nullable=False, server_default="log_only"),
        sa.Column("token", sa.String(64), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_integration_connections_organization_id", "integration_connections", ["organization_id"])

    op.create_table(
        "integration_mappings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("connection_id", sa.Uuid(), sa.ForeignKey("integration_connections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_field", sa.String(200), nullable=False),
        sa.Column("target_field", sa.String(200), nullable=False),
        sa.Column("transform", sa.String(50), nullable=True),
    )
    op.create_index("ix_integration_mappings_connection_id", "integration_mappings", ["connection_id"])

    op.create_table(
        "integration_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("connection_id", sa.Uuid(), sa.ForeignKey("integration_connections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", log_status_type, nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_integration_logs_connection_id", "integration_logs", ["connection_id"])
    op.create_index("ix_integration_logs_created_at", "integration_logs", ["created_at"])

    op.create_table(
        "airbyte_connections",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("airbyte_source_id", sa.String(100), nullable=False),
        sa.Column("airbyte_connection_id", sa.String(100), nullable=False),
        sa.Column("source_type", sa.String(100), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_airbyte_connections_organization_id", "airbyte_connections", ["organization_id"])


def downgrade() -> None:
    op.drop_table("airbyte_connections")
    op.drop_table("integration_logs")
    sa.Enum(name="integrationlogstatus").drop(op.get_bind(), checkfirst=True)
    op.drop_table("integration_mappings")
    op.drop_table("integration_connections")
    sa.Enum(name="integrationaction").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="integrationprovider").drop(op.get_bind(), checkfirst=True)

"""Phase 5, Étape 9 -- real, additive tables for MCP client config:
`mcp_server_configs` (org-scoped external MCP server registrations) and
`mcp_tool_cache` (their real, cached `tools/list` snapshot). See
api/models/mcp_server.py's own docstring for the real client/server
role split.

Reversible: `downgrade` drops both tables -- purely additive.

Revision ID: 0119
Revises: 0118
Create Date: 2026-09-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0119"
down_revision: Union[str, None] = "0118"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mcp_server_configs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("transport", sa.String(20), nullable=False),
        sa.Column("url", sa.String(2048), nullable=True),
        sa.Column("command", sa.String(500), nullable=True),
        sa.Column("args", sa.JSON(), nullable=False),
        sa.Column("env", sa.JSON(), nullable=False),
        sa.Column("auth_type", sa.String(20), nullable=False, server_default="none"),
        sa.Column("auth_credential_encrypted", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_error", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "name", name="uq_mcp_server_configs_org_name"),
    )
    op.create_index("ix_mcp_server_configs_organization_id", "mcp_server_configs", ["organization_id"])

    op.create_table(
        "mcp_tool_cache",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("server_id", sa.Uuid(), sa.ForeignKey("mcp_server_configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("input_schema", sa.JSON(), nullable=False),
        sa.Column("discovered_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("server_id", "name", name="uq_mcp_tool_cache_server_name"),
    )
    op.create_index("ix_mcp_tool_cache_server_id", "mcp_tool_cache", ["server_id"])


def downgrade() -> None:
    op.drop_table("mcp_tool_cache")
    op.drop_table("mcp_server_configs")

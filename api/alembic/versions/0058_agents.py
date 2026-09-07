"""add agents table (Partie 5.3.1-5.3.6)

Revision ID: 0058
Revises: 0057
Create Date: 2026-09-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0058"
down_revision: Union[str, None] = "0057"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("system_prompt_template", sa.Text(), nullable=True),
        sa.Column("model_config_json", sa.JSON(), nullable=False),
        sa.Column("tools", sa.JSON(), nullable=False),
        sa.Column("memory_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("memory_window_size", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("memory_ttl", sa.Integer(), nullable=True),
        sa.Column("memory_max_items", sa.Integer(), nullable=True),
        sa.Column("memory_retention_policy", sa.String(length=10), nullable=True),
        sa.Column("guardrails_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("human_approval_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("knowledge_base_id", sa.Uuid(), nullable=True),
        sa.Column("knowledge_base_config", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=10), nullable=False, server_default="active"),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["workspaces.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agents_organization_id", "agents", ["organization_id"])
    op.create_index("ix_agents_workspace_id", "agents", ["workspace_id"])
    op.execute("ALTER TABLE public.agents ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE public.agents DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_agents_workspace_id", table_name="agents")
    op.drop_index("ix_agents_organization_id", table_name="agents")
    op.drop_table("agents")

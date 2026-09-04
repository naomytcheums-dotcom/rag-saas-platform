"""add agent_sessions and agent_memory_items tables (Partie 5.1.11)

Revision ID: 0053
Revises: 0052
Create Date: 2026-09-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0053"
down_revision: Union[str, None] = "0052"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.String(length=200), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_sessions_agent_id", "agent_sessions", ["agent_id"])
    op.execute("ALTER TABLE public.agent_sessions ENABLE ROW LEVEL SECURITY")

    op.create_table(
        "agent_memory_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=200), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "key", name="uq_agent_memory_items_session_key"),
    )
    op.execute("ALTER TABLE public.agent_memory_items ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE public.agent_memory_items DISABLE ROW LEVEL SECURITY")
    op.drop_table("agent_memory_items")
    op.execute("ALTER TABLE public.agent_sessions DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_agent_sessions_agent_id", table_name="agent_sessions")
    op.drop_table("agent_sessions")

"""Phase 5, Étape 6 -- real, additive table: `agent_long_term_memory_items`,
cross-run agent memory distinct from the existing short-term
`agent_memory_items` (session-scoped, already real). See
api/models/agent_long_term_memory.py's own docstring for the real
`(agent_id, user_id, key)` uniqueness and why `expires_at` is nullable
here (defaults to "never expires", the opposite of short-term memory).

Reversible: `downgrade` drops the table -- purely additive, no existing
column touched.

Revision ID: 0118
Revises: 0117
Create Date: 2026-09-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0118"
down_revision: Union[str, None] = "0117"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_long_term_memory_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("agent_id", sa.Uuid(), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("key", sa.String(200), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("agent_id", "user_id", "key", name="uq_agent_long_term_memory_agent_user_key"),
    )
    op.create_index("ix_agent_long_term_memory_agent_id", "agent_long_term_memory_items", ["agent_id"])


def downgrade() -> None:
    op.drop_table("agent_long_term_memory_items")

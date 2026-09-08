"""add retry_count + regeneration_history + message_edit_history + message_feedback (Partie 8.1.6/8.1.7/8.1.8/8.1.9)

Revision ID: 0078
Revises: 0077
Create Date: 2026-09-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0078"
down_revision: Union[str, None] = "0077"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversation_messages",
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "regeneration_history",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("original_message_id", sa.Uuid(), sa.ForeignKey("conversation_messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("new_message_id", sa.Uuid(), sa.ForeignKey("conversation_messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("regenerated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_regeneration_history_original_message_id", "regeneration_history", ["original_message_id"])

    op.create_table(
        "message_edit_history",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("message_id", sa.Uuid(), sa.ForeignKey("conversation_messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("edited_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("edited_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_message_edit_history_message_id", "message_edit_history", ["message_id"])

    op.create_table(
        "message_feedback",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("message_id", sa.Uuid(), sa.ForeignKey("conversation_messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rating", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_message_feedback_message_id", "message_feedback", ["message_id"])
    op.create_index("ix_message_feedback_message_user_unique", "message_feedback", ["message_id", "user_id"], unique=True)


def downgrade() -> None:
    op.drop_table("message_feedback")
    op.drop_table("message_edit_history")
    op.drop_table("regeneration_history")
    op.drop_column("conversation_messages", "retry_count")

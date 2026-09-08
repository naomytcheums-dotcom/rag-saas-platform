"""add agents.* fields for 6.2.1/6.2.2/6.2.3 and responses.* fields for 6.2.5/6.2.11

Revision ID: 0070
Revises: 0069
Create Date: 2026-09-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0070"
down_revision: Union[str, None] = "0069"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("citation_required", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("agents", sa.Column("citation_required_message", sa.Text(), nullable=True))
    op.add_column("agents", sa.Column("answer_only_from_context", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("agents", sa.Column("context_only_message", sa.Text(), nullable=True))
    op.add_column("agents", sa.Column("idk_threshold", sa.Float(), nullable=True))
    op.add_column("agents", sa.Column("idk_message", sa.Text(), nullable=True))

    op.add_column("responses", sa.Column("has_unsupported_claims", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("responses", sa.Column("unsupported_claims", sa.JSON(), nullable=True))
    op.add_column("responses", sa.Column("faithfulness_score", sa.Float(), nullable=True))
    op.add_column("responses", sa.Column("faithfulness_factors", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("responses", "faithfulness_factors")
    op.drop_column("responses", "faithfulness_score")
    op.drop_column("responses", "unsupported_claims")
    op.drop_column("responses", "has_unsupported_claims")

    op.drop_column("agents", "idk_message")
    op.drop_column("agents", "idk_threshold")
    op.drop_column("agents", "context_only_message")
    op.drop_column("agents", "answer_only_from_context")
    op.drop_column("agents", "citation_required_message")
    op.drop_column("agents", "citation_required")

"""add agent guardrail fields (Partie 5.3.9)

Revision ID: 0060
Revises: 0059
Create Date: 2026-09-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0060"
down_revision: Union[str, None] = "0059"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("guardrails_config", sa.JSON(), nullable=True))
    op.add_column("agents", sa.Column("blocked_topics", sa.JSON(), nullable=True))
    op.add_column("agents", sa.Column("allowed_domains", sa.JSON(), nullable=True))
    op.add_column("agents", sa.Column("max_tokens_per_response", sa.Integer(), nullable=True))
    op.add_column("agents", sa.Column("content_filter_level", sa.String(length=10), nullable=True))


def downgrade() -> None:
    op.drop_column("agents", "content_filter_level")
    op.drop_column("agents", "max_tokens_per_response")
    op.drop_column("agents", "allowed_domains")
    op.drop_column("agents", "blocked_topics")
    op.drop_column("agents", "guardrails_config")

"""Phase 5, Étape 11 -- real, additive table: `retrieval_diagnostics`,
per-LIVE-query retrieval visibility (query/strategy/final chunks/
latency), distinct from Eval Lab's own `evaluation_results`. See
api/models/retrieval_diagnostic.py's own docstring for the honest,
deliberate scope.

Reversible: `downgrade` drops the table -- purely additive.

Revision ID: 0121
Revises: 0120
Create Date: 2026-09-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0121"
down_revision: Union[str, None] = "0120"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "retrieval_diagnostics",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("strategy", sa.String(30), nullable=False),
        sa.Column("final_chunks", sa.JSON(), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_retrieval_diagnostics_organization_id", "retrieval_diagnostics", ["organization_id"])


def downgrade() -> None:
    op.drop_table("retrieval_diagnostics")

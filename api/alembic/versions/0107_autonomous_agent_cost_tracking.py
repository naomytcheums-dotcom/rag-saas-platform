"""Partie 23 (cost tracking finalization) -- real, per-step and
per-agent USD cost accumulation. See
api/services/autonomous_agents.py's own module docstring for exactly
which real LLM calls are costed (reusing the pre-existing
api.services.cost_tracking.calculate_cost_per_request pricing table).

Revision ID: 0107
Revises: 0106
Create Date: 2026-09-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0107"
down_revision: Union[str, None] = "0106"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("autonomous_agents", sa.Column("total_cost", sa.Numeric(12, 6), nullable=False, server_default="0"))
    op.add_column("agent_steps", sa.Column("total_cost", sa.Numeric(12, 6), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("agent_steps", "total_cost")
    op.drop_column("autonomous_agents", "total_cost")

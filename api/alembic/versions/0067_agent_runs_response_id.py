"""add agent_runs.response_id (Partie 6.1.1 orchestrator integration)

Revision ID: 0067
Revises: 0066
Create Date: 2026-09-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0067"
down_revision: Union[str, None] = "0066"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agent_runs", sa.Column("response_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_agent_runs_response_id", "agent_runs", "responses", ["response_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_agent_runs_response_id", "agent_runs", type_="foreignkey")
    op.drop_column("agent_runs", "response_id")

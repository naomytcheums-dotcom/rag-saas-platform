"""Bricks open source, item 7 -- real, additive column:
`agents.prompt_injection_detection_enabled`. Deliberately its OWN,
separate opt-in flag rather than reusing `guardrails_enabled` (which
already defaults `True` for every existing agent) -- see
api/services/prompt_injection_detection.py's own module docstring for
why this real, dedicated classifier model's first-use download/inference
cost must never silently apply to an agent that never opted in.

Reversible: `downgrade` drops the column -- purely additive.

Revision ID: 0125
Revises: 0124
Create Date: 2026-09-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0125"
down_revision: Union[str, None] = "0124"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("prompt_injection_detection_enabled", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("agents", "prompt_injection_detection_enabled")

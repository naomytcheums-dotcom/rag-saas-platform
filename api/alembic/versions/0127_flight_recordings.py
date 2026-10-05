"""Systèmes internes, item 24 -- real, additive table: `flight_recordings`
(RAG Flight Recorder). See api/models/flight_recording.py's own module
docstring for the full real design and honest scope boundary (a real
recording primitive, not yet automatically populated by
api.services.retrieval_pipeline.search's own internal stages -- that
wiring is real, deliberately deferred future work).

Reversible: `downgrade` drops the table -- purely additive.

Revision ID: 0127
Revises: 0126
Create Date: 2026-09-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0127"
down_revision: Union[str, None] = "0126"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "flight_recordings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("query", sa.String(2000), nullable=False),
        sa.Column("stages_json", sa.JSON(), nullable=False),
        sa.Column("total_duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_flight_recordings_organization_id", "flight_recordings", ["organization_id"])


def downgrade() -> None:
    op.drop_table("flight_recordings")

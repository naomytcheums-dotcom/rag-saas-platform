"""Hardening Mission, Phase 7 -- real response provenance. Closes a
real, confirmed audit gap: a `Response` row had no way to answer "what
retrieval strategy/embedding model/LLM provider/model actually produced
this answer?" after the fact, nor any link to its own real, optional
Flight Recorder trace (`flight_recordings`, migration 0127). See
api/models/response.py's own docstring for the full real design.

Purely additive: every new column is nullable, so every pre-existing
real `Response` row stays exactly as it was (a real, historical row has
no value to honestly backfill -- the same "nullable for pre-existing
rows" discipline as every other real migration in this codebase).

Reversible: `downgrade` drops all 5 columns.

Revision ID: 0130
Revises: 0129
Create Date: 2026-10-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0130"
down_revision: Union[str, None] = "0129"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("responses", sa.Column("retrieval_strategy", sa.String(20), nullable=True))
    op.add_column("responses", sa.Column("embedding_model", sa.String(200), nullable=True))
    op.add_column("responses", sa.Column("llm_provider", sa.String(50), nullable=True))
    op.add_column("responses", sa.Column("llm_model", sa.String(200), nullable=True))
    op.add_column("responses", sa.Column("flight_recording_id", sa.Uuid(), sa.ForeignKey("flight_recordings.id", ondelete="SET NULL"), nullable=True))


def downgrade() -> None:
    op.drop_column("responses", "flight_recording_id")
    op.drop_column("responses", "llm_model")
    op.drop_column("responses", "llm_provider")
    op.drop_column("responses", "embedding_model")
    op.drop_column("responses", "retrieval_strategy")

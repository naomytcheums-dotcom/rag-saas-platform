"""Phase 4, Étape 1 (correctif parent_child) -- one-time data backfill
for the real bug fixed alongside this migration in
`api/models/document.py`'s own `DocumentChunk.embedding` column
docstring: a plain `JSON` type (before this fix) bound a Python `None`
as the JSON literal `null`, not a real SQL `NULL`, so any real,
existing row whose embedding genuinely failed to generate (a real,
pre-existing, documented, legitimate state -- see that column's own
docstring) may already be storing a literal JSON `null` in production,
silently defeating `DocumentChunk.embedding.is_not(None)` -- the SAME
real filter every retrieval strategy in `api/services/retrieval_pipeline.py`
relies on to keep an unembedded chunk out of search.

Real, idempotent, additive-only: converts any such row to a real SQL
`NULL` (its own real, intended meaning all along); a row that already
has a genuine embedding, or already has a real SQL `NULL`, is
untouched. Safe to run more than once.

Revision ID: 0113
Revises: 0112
Create Date: 2026-09-22
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0113"
down_revision: Union[str, None] = "0112"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE document_chunks SET embedding = NULL WHERE embedding::text = 'null'")


def downgrade() -> None:
    # Real, honest no-op: a real SQL NULL and a real JSON literal `null`
    # were always meant to represent the exact same real thing ("no
    # embedding") -- there is no real, meaningful state to revert to.
    pass

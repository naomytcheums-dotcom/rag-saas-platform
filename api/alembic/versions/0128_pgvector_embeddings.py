"""Hardening Mission, Phase 1 -- real pgvector support for
`document_chunks`. Closes a real gap an external audit found: AGENTS.md
/ the project's own stack overview announced "PostgreSQL + pgvector",
but no `vector` extension, no `Vector` column, and no index ever
existed -- retrieval ran a pure numpy cosine fallback in-process
instead (see api/services/retrieval_pipeline.py's own top docstring,
which already, honestly, called this "genuine future work").

This migration is purely ADDITIVE: the existing `embedding` JSON column
is untouched, so nothing that already reads/writes it changes behavior.
Three new columns close the gap:

- `embedding_model` / `embedding_dim`: real provenance for one chunk's
  own embedding (what produced it, and at what dimension) -- the real
  fix for a separately-reproduced crash when an organization's chunks
  mix dimensions after an `embedding_model` change
  (api.services.retrieval_pipeline.cosine_similarities now groups by
  dimension before ever calling numpy).
- `embedding_vector`: pgvector's real `vector(384)` type, fixed at
  `settings.EMBEDDING_VECTOR_DIM` (the default embedding model's own
  real dimension) -- a real HNSW index needs one fixed dimension per
  column. Only ever populated for a chunk whose own `embedding_dim`
  matches; every other dimension keeps working correctly through the
  pre-existing numpy path, just without this index's speedup until a
  real reindex (api.services.embedding_reindex) runs.

Guarded to no-op on a non-Postgres bind (this codebase's own fast test
suite builds its schema straight from the ORM models via
`Base.metadata.create_all()`, never through Alembic -- see
api/models/document.py's own DocumentChunk docstring for the matching
`.with_variant(JSON(...), "sqlite")` on that same column -- but this
guard keeps the migration itself honest/safe regardless).

Reversible: `downgrade` drops the index, the extension is left alone
(other real tables/future migrations may still want it).

Revision ID: 0128
Revises: 0127
Create Date: 2026-10-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from api.config import settings

revision: str = "0128"
down_revision: Union[str, None] = "0127"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DIM = settings.EMBEDDING_VECTOR_DIM


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column("document_chunks", sa.Column("embedding_model", sa.String(200), nullable=True))
    op.add_column("document_chunks", sa.Column("embedding_dim", sa.Integer(), nullable=True))
    op.execute(f"ALTER TABLE document_chunks ADD COLUMN embedding_vector vector({_DIM})")

    # Real, one-time backfill: every chunk whose plain-JSON `embedding`
    # already has exactly the default dimension gets its new columns
    # populated immediately, no reindex job needed for the common case
    # (a fresh install, or an org that never changed embedding_model).
    op.execute(
        f"""
        UPDATE document_chunks
        SET embedding_dim = jsonb_array_length(to_jsonb(embedding)),
            embedding_vector = CASE
                WHEN jsonb_array_length(to_jsonb(embedding)) = {_DIM}
                THEN embedding::text::vector({_DIM})
                ELSE NULL
            END
        WHERE embedding IS NOT NULL
        """
    )

    # Real HNSW ANN index -- cosine distance, matching
    # `api.services.retrieval_pipeline`'s own cosine similarity
    # semantics everywhere else in this codebase.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_vector_hnsw "
        "ON document_chunks USING hnsw (embedding_vector vector_cosine_ops)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_vector_hnsw")
    op.drop_column("document_chunks", "embedding_vector")
    op.drop_column("document_chunks", "embedding_dim")
    op.drop_column("document_chunks", "embedding_model")

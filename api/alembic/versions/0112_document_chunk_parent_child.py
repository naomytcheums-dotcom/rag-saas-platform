"""Phase 4, Étape 1 (correctif) -- the real persisted parent/child
relationship `DocumentChunk` needed to actually wire the
`"parent_child"` chunking strategy into production, instead of just
selecting it and silently falling back.

Two purely additive columns:

- `parent_chunk_id` (self-referential FK on `document_chunks.id`,
  `ON DELETE CASCADE`, nullable): the real, small unit's own real, wider
  parent -- `NULL` for every chunk produced by any of the other 7
  strategies (unchanged), and for a parent chunk itself (a parent has
  no parent of its own). `ON DELETE CASCADE` keeps a real child from
  ever outliving its own real parent (mirroring the SAME real cascade
  `document_id`'s own FK already applies at the whole-document level) --
  a genuine document delete/reindex already deletes every real chunk
  row for that document wholesale (`DELETE ... WHERE document_id = ...`,
  `api/security/documents.py`'s own `process_document`), so this
  cascade only ever matters for a real, targeted single-chunk delete
  path, if one is ever added later; it costs nothing to have it correct
  from the start.
- `chunk_role` (nullable string, `"parent"` / `"child"` / `NULL`): a
  real, explicit tag -- `NULL` for every one of the other 7 strategies'
  own chunks (unchanged), so this migration never reinterprets any
  real, existing row. A real, deliberate choice over inferring the role
  from `embedding IS NULL` alone: `embedding` can already be `NULL` for
  an unrelated, real reason (embedding generation genuinely failed or
  simply hasn't run yet, see `DocumentChunk.embedding`'s own module
  docstring) -- conflating that with "this is a parent, by design" would
  be a real, silent misclassification.

Revision ID: 0112
Revises: 0111
Create Date: 2026-09-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0112"
down_revision: Union[str, None] = "0111"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("document_chunks", sa.Column("parent_chunk_id", sa.Uuid(), nullable=True))
    op.add_column("document_chunks", sa.Column("chunk_role", sa.String(length=10), nullable=True))
    op.create_foreign_key(
        "fk_document_chunks_parent_chunk_id", "document_chunks", "document_chunks",
        ["parent_chunk_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("ix_document_chunks_parent_chunk_id", "document_chunks", ["parent_chunk_id"])


def downgrade() -> None:
    op.drop_index("ix_document_chunks_parent_chunk_id", table_name="document_chunks")
    op.drop_constraint("fk_document_chunks_parent_chunk_id", "document_chunks", type_="foreignkey")
    op.drop_column("document_chunks", "chunk_role")
    op.drop_column("document_chunks", "parent_chunk_id")

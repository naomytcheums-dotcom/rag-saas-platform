# Analyse détaillée — migration Alembic 0128 (pgvector)

Analyse statique du fichier présent dans le workspace, date 2026-10-03. Aucun
accès PostgreSQL, upgrade, downgrade ou EXPLAIN exécuté.

## 1. Contenu complet de `0128_pgvector_embeddings.py`

Copie du fichier observé sous `api/alembic/versions/0128_pgvector_embeddings.py` :

```python
"""Hardening Mission, Phase 1 -- real pgvector support for
`document_chunks`. Closes a real gap an external audit found: AGENTS.md
/ the project's own stack overview announced "PostgreSQL + pgvector",
but no `vector` extension, no `Vector` column, and no index ever
existed -- retrieval ran a pure numpy cosine fallback in-process
instead (see api/services/retrieval_pipeline.py's own top docstring,
which already, honestly, called this "genuine future work").

This migration is purely ADDITIVE: the existing `embedding` JSON column
is untouched, so nothing that already reads/writes it changes behavior.
Three new columns close the real gap:

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
```

The source is present in the workspace under `api/alembic/versions/`, but is
not tracked at the initial Git HEAD in the recorded Phase 2 baseline. The copy
above follows the local source and may not match a deployed revision.

## 2. Type de migration

The declared upgrade is **additive for existing application data**: it keeps
the old JSON embedding column and adds extension/type/index/columns; only rows
with a non-NULL embedding are transformed into the new representation. It is
also an operationally substantial migration because it updates existing rows
and builds an ANN index. Its downgrade is data-destructive for the new
representation and provenance columns, although it leaves the old JSON
embedding and vector extension intact.

## 3. Colonnes ajoutées

| Column | Type | Nullable | Populated by |
|---|---|---|---|
| `document_chunks.embedding_model` | `VARCHAR(200)` | Yes | Not assigned by this migration; remains `NULL` unless another application/reindex path writes it |
| `document_chunks.embedding_dim` | `INTEGER` | Yes | Backfill sets JSON array length for non-NULL embedding; application writes may also set it |
| `document_chunks.embedding_vector` | PostgreSQL `vector(_DIM)` | Yes by absence of `NOT NULL` | Backfill only when dimension equals `_DIM`; other rows NULL |

The existing `document_chunks.embedding` JSON column is not dropped or
rewritten by this migration.

## 4. Indexes and operator class

- Creates `ix_document_chunks_embedding_vector_hnsw`.
- Access method: `USING hnsw`.
- Operator class: `vector_cosine_ops`; this supports cosine-distance
  approximate nearest-neighbor use.
- No IVFFlat index is declared.
- There is no `CONCURRENTLY`; Alembic normally executes migrations inside a
  transaction on PostgreSQL. Index build duration and write blocking depend on
  table size, server resources and PostgreSQL/pgvector version; those are
  **UNKNOWN** for the target.

## 5. `USING` operation

The migration contains:

```sql
CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_vector_hnsw
ON document_chunks USING hnsw (embedding_vector vector_cosine_ops)
```

This `USING hnsw` selects the pgvector HNSW index access method. The SQL is
issued only if `op.get_bind().dialect.name == "postgresql"`.

## 6. Vector dimension

`_DIM` is read from `settings.EMBEDDING_VECTOR_DIM`. The local model comments
and source describe the default as **384**, but the setting can be overridden
by deployment configuration. Actual effective value for any target is
**UNKNOWN**; this audit did not read `.env` or connect to a DB.

## 7. Backfill strategy

The migration performs one in-place `UPDATE document_chunks` of all rows with
`embedding IS NOT NULL`:

- `embedding_dim = jsonb_array_length(to_jsonb(embedding))`
- `embedding_vector` converts `embedding::text::vector(_DIM)` only when the
  JSON array length equals `_DIM`; otherwise it leaves the vector column NULL.
- rows whose old embedding is NULL are skipped and keep new values NULL.
- `embedding_model` is not inferred/backfilled.
- a malformed/non-array JSON value can make `jsonb_array_length` fail.
- an array with malformed/non-numeric/non-finite members, or vector text
  incompatible with pgvector input, can make the cast fail.
- an empty/other-dimension array will not populate vector when length differs,
  but the JSON array-length expression still runs.
- all old JSON values remain in place.

## 8. Risks and rollback

| Risk | Assessment from source | Evidence still required |
|---|---|---|
| Invalid embeddings | `jsonb_array_length` and vector cast can abort migration on unexpected JSON shape or invalid vector members | Read-only data-quality profile on an identified, approved staging clone |
| Wrong/mixed dimensions | Rows whose length differs from configured `_DIM` intentionally receive NULL vector; only same-dimension rows use HNSW | Verify effective setting, model dimensions, proportions and fallback path |
| NULL embeddings | Excluded by `WHERE embedding IS NOT NULL`; new fields remain nullable | Confirm app query handles NULL vector and JSON fallback |
| Large table lock | `ALTER TABLE`, full-table `UPDATE`, then index build may lock/heavily load table | Table size, lock timeout, maintenance window, realistic staging rehearsal |
| Long migration | Full backfill plus HNSW build are synchronous in upgrade | Measured duration on representative clone; statement timeout |
| Index cost | HNSW build uses memory/CPU/storage and is not concurrent in this source | Disk headroom and measured build profile |
| Rollback | Drops index and three columns; extension remains. Vector backfill/provenance is lost, but original JSON embeddings remain | Confirm no code depends exclusively on new columns before downgrade |
| Transaction/extension | Extension creation permission and extension/version requirements may fail | Extension installed/version/privilege checks on approved target |

Rollback is syntactically available, but a downgrade is **not** a general
production rollback: it discards new vector/index/model/dimension state and
can lock the table again.

## 9. Safe rollout proposal

1. **Expand:** on a disposable staging clone, verify pgvector version,
   privileges, effective dimension, table size, JSON shape and rollback plan.
   Add nullable metadata/vector columns; do not change retrieval reads yet.
2. **Backfill:** move large-table backfill to bounded batches with resumable
   progress if volume/lock testing shows the single UPDATE is unsafe; retain
   the JSON source and record invalid/mismatched rows rather than aborting
   without diagnostics.
3. **Validate:** compare each non-null vector dimension with `_DIM`, count
   null/mismatched/invalid rows, compare cosine rankings to the old path and
   ensure tenant/document filters are preserved.
4. **Index:** create HNSW after representative load testing; use a deliberate
   online/concurrent index strategy if supported by deployed PostgreSQL/
   pgvector and migration transaction policy.
5. **Switch:** feature-gate pgvector retrieval; run `EXPLAIN (ANALYZE, BUFFERS)`
   and recall/latency benchmark with a tenant-specific approved dataset.
   Retain JSON fallback and rollback until acceptance thresholds pass.
6. **Promote:** only after the destination is explicitly identified, proven
   recoverable and approved. No live mutation is authorized by this report.

This is a recommendation, not an implemented migration plan or measured
benchmark.

## 10. Application status

**Migration applied: UNKNOWN.** The local Alembic source graph before the
pending Phase 2 addition ended at 0131; 0128 was locally present but
untracked. The target database revision, extension, column and index state
were not queried. A prior `alembic current` attempt failed without a useful
revision; no retry/connection was made in this phase. Do not infer applied or
not applied from local source files.

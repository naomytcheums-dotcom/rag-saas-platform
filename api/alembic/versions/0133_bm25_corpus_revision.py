"""Transactional BM25 corpus revisions, including writes from other processes.

Revision ID: 0133
Revises: 0132
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0133"
down_revision: str | None = "0132"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("documents", "document_chunks", "media_assets")
_OPERATIONS = {
    "insert": ("NEW TABLE AS new_rows", "SELECT organization_id FROM new_rows"),
    "delete": ("OLD TABLE AS old_rows", "SELECT organization_id FROM old_rows"),
    "update": (
        "OLD TABLE AS old_rows NEW TABLE AS new_rows",
        "SELECT organization_id FROM old_rows UNION SELECT organization_id FROM new_rows",
    ),
}


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("bm25_corpus_revision", sa.BigInteger(), nullable=False, server_default="0"),
    )
    # One update per affected organization per SQL statement, not per chunk.
    # Invoker rights preserve the existing tenant RLS; no SECURITY DEFINER.
    for operation, (referencing, organizations) in _OPERATIONS.items():
        op.execute(f"""
            CREATE FUNCTION bm25_revision_{operation}() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                UPDATE organizations
                SET bm25_corpus_revision = bm25_corpus_revision + 1
                WHERE id IN ({organizations});
                RETURN NULL;
            END;
            $$
        """)
        for table in _TABLES:
            op.execute(
                f"CREATE TRIGGER bm25_revision_{table}_{operation} "
                f"AFTER {operation.upper()} ON {table} REFERENCING {referencing} "
                f"FOR EACH STATEMENT EXECUTE FUNCTION bm25_revision_{operation}()"
            )


def downgrade() -> None:
    for operation in _OPERATIONS:
        for table in _TABLES:
            op.execute(f"DROP TRIGGER bm25_revision_{table}_{operation} ON {table}")
        op.execute(f"DROP FUNCTION bm25_revision_{operation}()")
    op.drop_column("organizations", "bm25_corpus_revision")

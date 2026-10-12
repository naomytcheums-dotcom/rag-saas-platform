"""BM25 corpus revisions bumped once per transaction, at commit, instead of once per statement.

Revision ID: 0144
Revises: 0143

0133 updated `organizations.bm25_corpus_revision` from statement-level triggers: the first write of a transaction took a row lock on the organization that was
held until the transaction ended, so every other transaction writing documents, chunks or media for the SAME organization waited for it (measured 2026-10-12
on a disposable database: 4 s of waiting while another organization did not wait). Ingestion of several documents of one organization was therefore serialized.

Here the triggers are DEFERRABLE INITIALLY DEFERRED constraint triggers: they run at COMMIT, inside the committing transaction, so the revision still changes
atomically with the corpus (what the BM25 index cache relies on), but the lock lasts only for the instant of the commit. A transaction-local setting remembers the
organizations already bumped, so the revision moves by one per transaction and organization however many rows were written. Invoker rights, as in 0133 (tenant
RLS is preserved, no SECURITY DEFINER). The SQLite equivalent used by the tests is unchanged. The downgrade restores the exact triggers of 0133.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0144"
down_revision: str | None = "0143"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("documents", "document_chunks", "media_assets")
_OPERATIONS = ("insert", "delete", "update")

# The statement-level triggers of 0133, restored by downgrade().
_LEGACY = {
    "insert": ("NEW TABLE AS new_rows", "SELECT organization_id FROM new_rows"),
    "delete": ("OLD TABLE AS old_rows", "SELECT organization_id FROM old_rows"),
    "update": (
        "OLD TABLE AS old_rows NEW TABLE AS new_rows",
        "SELECT organization_id FROM old_rows UNION SELECT organization_id FROM new_rows",
    ),
}


def upgrade() -> None:
    for operation in _OPERATIONS:
        for table in _TABLES:
            op.execute(f"DROP TRIGGER bm25_revision_{table}_{operation} ON {table}")
        op.execute(f"DROP FUNCTION bm25_revision_{operation}()")
    op.execute("""
        CREATE FUNCTION bm25_revision_bump_org(org uuid) RETURNS void
        LANGUAGE plpgsql AS $$
        DECLARE seen text := coalesce(current_setting('rag.bm25_bumped', true), '');
        BEGIN
            IF org IS NULL OR position(org::text IN seen) > 0 THEN
                RETURN;
            END IF;
            PERFORM set_config('rag.bm25_bumped', seen || ',' || org::text, true);
            UPDATE organizations SET bm25_corpus_revision = bm25_corpus_revision + 1 WHERE id = org;
        END;
        $$
    """)
    op.execute("""
        CREATE FUNCTION bm25_revision_bump() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP IN ('UPDATE', 'DELETE') THEN
                PERFORM bm25_revision_bump_org(OLD.organization_id);
            END IF;
            IF TG_OP = 'INSERT' OR (TG_OP = 'UPDATE' AND NEW.organization_id IS DISTINCT FROM OLD.organization_id) THEN
                PERFORM bm25_revision_bump_org(NEW.organization_id);
            END IF;
            RETURN NULL;
        END;
        $$
    """)
    for table in _TABLES:
        for operation in _OPERATIONS:
            op.execute(
                f"CREATE CONSTRAINT TRIGGER bm25_revision_{table}_{operation} "
                f"AFTER {operation.upper()} ON {table} DEFERRABLE INITIALLY DEFERRED "
                "FOR EACH ROW EXECUTE FUNCTION bm25_revision_bump()"
            )


def downgrade() -> None:
    for operation in _OPERATIONS:
        for table in _TABLES:
            op.execute(f"DROP TRIGGER bm25_revision_{table}_{operation} ON {table}")
    op.execute("DROP FUNCTION bm25_revision_bump()")
    op.execute("DROP FUNCTION bm25_revision_bump_org(uuid)")
    for operation, (referencing, organizations) in _LEGACY.items():
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

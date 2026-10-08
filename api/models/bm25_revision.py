"""SQLite equivalents of migration 0133's transactional corpus revisions."""

from sqlalchemy import DDL, event

from api.models.document import Document, DocumentChunk
from api.models.media import MediaAsset


for model in (Document, DocumentChunk, MediaAsset):
    table = model.__table__
    for operation, aliases in (
        ("insert", ("NEW",)),
        ("delete", ("OLD",)),
        ("update", ("OLD", "NEW")),
    ):
        organizations = " OR ".join(f"id = {alias}.organization_id" for alias in aliases)
        event.listen(
            table,
            "after_create",
            DDL(
                f"CREATE TRIGGER bm25_revision_{table.name}_{operation} "
                f"AFTER {operation.upper()} ON {table.name} BEGIN "
                "UPDATE organizations SET bm25_corpus_revision = bm25_corpus_revision + 1 "
                f"WHERE {organizations}; END"
            ).execute_if(dialect="sqlite"),
        )

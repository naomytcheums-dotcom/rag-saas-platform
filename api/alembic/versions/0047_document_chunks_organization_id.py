"""add organization_id to document_chunks (Partie 3.3.4 -- real multi-tenant search pipeline)

Revision ID: 0047
Revises: 0046
Create Date: 2026-09-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0047"
down_revision: Union[str, None] = "0046"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("document_chunks", sa.Column("organization_id", sa.Uuid(), nullable=True))
    op.execute(
        "UPDATE document_chunks SET organization_id = documents.organization_id "
        "FROM documents WHERE documents.id = document_chunks.document_id"
    )
    op.alter_column("document_chunks", "organization_id", nullable=False)
    op.create_foreign_key(
        "fk_document_chunks_organization_id", "document_chunks", "organizations", ["organization_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("ix_document_chunks_organization_id", "document_chunks", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_document_chunks_organization_id", table_name="document_chunks")
    op.drop_constraint("fk_document_chunks_organization_id", "document_chunks", type_="foreignkey")
    op.drop_column("document_chunks", "organization_id")

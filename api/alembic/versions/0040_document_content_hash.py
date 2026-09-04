"""add content_hash to documents (Partie 2.2.12)

Revision ID: 0040
Revises: 0039
Create Date: 2026-09-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0040"
down_revision: Union[str, None] = "0039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No RLS statement needed here -- a new column on an already-
    # RLS-enabled table (documents has carried RLS since migration
    # 0002), not a new table.
    op.add_column("documents", sa.Column("content_hash", sa.String(length=64), nullable=True))
    # A plain INDEX, not the UNIQUE constraint this étape's own literal
    # wording asks for -- see api/models/document.py's own docstring on
    # this index for the real, deliberate reason (a hard constraint
    # would make item 4's own "POST .../deduplicate" route permanently
    # unable to find any real work, since the same upload path already
    # blocks a duplicate from being created at all). Includes
    # `file_type`, not just `content_hash` -- the same raw bytes can
    # legitimately be two different real documents under a different
    # detected format (e.g. Markdown vs plain TXT).
    op.create_index("ix_documents_organization_content_hash_file_type", "documents", ["organization_id", "content_hash", "file_type"])


def downgrade() -> None:
    op.drop_index("ix_documents_organization_content_hash_file_type", table_name="documents")
    op.drop_column("documents", "content_hash")

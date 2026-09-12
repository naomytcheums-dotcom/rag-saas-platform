"""Partie 22, 3rd finalization -- CLIP-based visual search: adds
media_assets.clip_embedding (a real, plain JSON float-list embedding,
same convention as document_chunks.embedding).

Revision ID: 0105
Revises: 0104
Create Date: 2026-09-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0105"
down_revision: Union[str, None] = "0104"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("media_assets", sa.Column("clip_embedding", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("media_assets", "clip_embedding")

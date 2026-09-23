"""Phase 5, Étape 5 -- real, minimal, additive column:
`workflows.variables`, a JSON list of named variable definitions
(name/type/default_value/description/scope). NULL-free by design: a
new column with `server_default='[]'` means every pre-existing
workflow row gets a real, empty list immediately, not NULL -- the
runtime code (`api/services/workflow_engine.py`) always iterates it
without a None-check.

Reversible: `downgrade` drops the column -- additive-only, no other
column depends on it.

Revision ID: 0117
Revises: 0116
Create Date: 2026-09-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0117"
down_revision: Union[str, None] = "0116"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("workflows", sa.Column("variables", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    op.drop_column("workflows", "variables")

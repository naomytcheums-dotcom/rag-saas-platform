"""Phase 4, Étape 5 (Domain Allowlist Widget) -- real, minimal, additive
column: `widget_configs.allowed_domains`, a real, optional, per-
organization JSON list of origins allowed to embed/call this
organization's own widget. `NULL` (every real, pre-existing row's own
real value after this migration -- no backfill needed, a new nullable
column defaults every existing row to `NULL` already) means the exact
same real, unrestricted behavior this codebase's widget already had
before this étape (see api/models/widget.py's own updated docstring).

Reversible: `downgrade` drops the column -- a real, additive-only
change with no other real column depending on it.

Revision ID: 0114
Revises: 0113
Create Date: 2026-09-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0114"
down_revision: Union[str, None] = "0113"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("widget_configs", sa.Column("allowed_domains", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("widget_configs", "allowed_domains")

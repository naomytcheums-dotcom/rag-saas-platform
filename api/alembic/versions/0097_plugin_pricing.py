"""Partie 16 (ter), extended -- plugins.pricing, plugins.price.

Revision ID: 0097
Revises: 0096
Create Date: 2026-09-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0097"
down_revision: Union[str, None] = "0096"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    plugin_pricing = sa.Enum("free", "paid", "freemium", name="pluginpricing")
    plugin_pricing.create(op.get_bind(), checkfirst=True)  # add_column does not auto-create an enum type -- see migration 0096's own real bug/fix
    op.add_column("plugins", sa.Column("pricing", plugin_pricing, nullable=False, server_default="free"))
    op.add_column("plugins", sa.Column("price", sa.Numeric(10, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("plugins", "price")
    op.drop_column("plugins", "pricing")
    sa.Enum(name="pluginpricing").drop(op.get_bind(), checkfirst=True)

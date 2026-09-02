"""add custom_domains (Partie 1.4.1)

Revision ID: 0026
Revises: 0025
Create Date: 2026-09-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: Union[str, None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "custom_domains",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("verification_token", sa.String(length=64), nullable=False),
        sa.Column("ssl_cert", sa.Text(), nullable=True),
        sa.Column("ssl_key", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint("uq_custom_domains_domain", "custom_domains", ["domain"])
    op.create_index("ix_custom_domains_organization_id", "custom_domains", ["organization_id"])
    op.execute("ALTER TABLE public.custom_domains ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("ix_custom_domains_organization_id", table_name="custom_domains")
    op.drop_table("custom_domains")

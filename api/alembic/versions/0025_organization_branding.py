"""add organization_branding (Partie 1.3.10)

Revision ID: 0025
Revises: 0024
Create Date: 2026-09-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organization_branding",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("favicon_url", sa.Text(), nullable=True),
        sa.Column("primary_color", sa.String(length=7), nullable=False, server_default="#2563eb"),
        sa.Column("secondary_color", sa.String(length=7), nullable=False, server_default="#1e293b"),
        sa.Column("accent_color", sa.String(length=7), nullable=False, server_default="#f59e0b"),
        sa.Column("font_family", sa.String(length=100), nullable=False, server_default="Inter"),
        sa.Column("brand_name", sa.String(length=200), nullable=True),
        sa.Column("custom_css", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint("uq_organization_branding_organization_id", "organization_branding", ["organization_id"])
    op.execute("ALTER TABLE public.organization_branding ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("organization_branding")

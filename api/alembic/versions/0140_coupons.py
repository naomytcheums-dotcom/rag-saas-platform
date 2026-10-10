"""Promo codes: `coupons` and `coupon_redemptions` (spec 12.1.4). Additive and reversible; row level security enabled like every table since 0131.

Revision ID: 0140
Revises: 0139
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0140"
down_revision: str | None = "0139"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "coupons",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("bonus_credits", sa.Integer(), nullable=True),
        sa.Column("percent_off", sa.Integer(), nullable=True),
        sa.Column("max_redemptions", sa.Integer(), nullable=True),
        sa.Column("redeemed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_coupons_code", "coupons", ["code"], unique=True)
    op.create_table(
        "coupon_redemptions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("coupon_id", sa.Uuid(), sa.ForeignKey("coupons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("coupon_id", "organization_id", name="uq_coupon_redemption_once_per_org"),
    )
    op.create_index("ix_coupon_redemptions_coupon_id", "coupon_redemptions", ["coupon_id"])
    op.create_index("ix_coupon_redemptions_organization_id", "coupon_redemptions", ["organization_id"])
    op.execute("ALTER TABLE coupons ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE coupon_redemptions ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("coupon_redemptions")
    op.drop_table("coupons")

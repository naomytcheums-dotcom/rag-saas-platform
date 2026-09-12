"""Partie 18 -- partner_commissions: the real, persisted commission
ledger calculate_reseller_commission (Partie 16 bis) deliberately left
as a live calculation only.

Revision ID: 0099
Revises: 0098
Create Date: 2026-09-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PGEnum

revision: str = "0099"
down_revision: Union[str, None] = "0098"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Real, self-inflicted DuplicateObjectError hit live, twice, against
    # this deployment's real Supabase Postgres (pooled via Supavisor):
    # neither `sa.Enum(...).create(checkfirst=True)` nor a raw idempotent
    # `DO $$ ... EXCEPTION WHEN duplicate_object` block stopped
    # create_table's own column-type DDL from ALSO trying to CREATE TYPE
    # for the generic `sa.Enum`. The dialect-specific `postgresql.ENUM`
    # with `create_type=False` is the one type object that reliably
    # means "reference this existing type, never emit CREATE TYPE for
    # it" -- create it explicitly once above, reference-only below.
    op.execute("DO $$ BEGIN CREATE TYPE partnercommissionstatus AS ENUM ('pending', 'paid'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
    partner_commission_status_col = PGEnum("pending", "paid", name="partnercommissionstatus", create_type=False)

    op.create_table(
        "partner_commissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("reseller_id", sa.Uuid(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("status", partner_commission_status_col, nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["reseller_id"], ["resellers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_partner_commissions_reseller_id", "partner_commissions", ["reseller_id"])
    # Learned the hard way (migration 0098): every table this app creates
    # gets this line, in the SAME migration that creates it, not added
    # later as a separate sweep.
    op.execute("ALTER TABLE public.partner_commissions ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("ix_partner_commissions_reseller_id", table_name="partner_commissions")
    op.drop_table("partner_commissions")
    sa.Enum(name="partnercommissionstatus").drop(op.get_bind(), checkfirst=True)

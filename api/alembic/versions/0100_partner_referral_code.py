"""Partie 18 (referral link) -- resellers.referral_code, a real, random,
unique per-partner code for self-service client attribution.

Revision ID: 0100
Revises: 0099
Create Date: 2026-09-20
"""

import secrets
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0100"
down_revision: Union[str, None] = "0099"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("resellers", sa.Column("referral_code", sa.String(length=16), nullable=True))

    # Backfill any real, pre-existing reseller rows (this dev deployment
    # has none, but a self-hosted install applying this migration might)
    # -- one real, unique code per row, not a shared placeholder.
    conn = op.get_bind()
    reseller_ids = [row[0] for row in conn.execute(sa.text("SELECT id FROM resellers")).fetchall()]
    for reseller_id in reseller_ids:
        conn.execute(sa.text("UPDATE resellers SET referral_code = :code WHERE id = :id"), {"code": secrets.token_hex(4), "id": reseller_id})

    op.alter_column("resellers", "referral_code", nullable=False)
    op.create_unique_constraint("uq_resellers_referral_code", "resellers", ["referral_code"])


def downgrade() -> None:
    op.drop_constraint("uq_resellers_referral_code", "resellers", type_="unique")
    op.drop_column("resellers", "referral_code")

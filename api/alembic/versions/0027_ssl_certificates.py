"""add acme_accounts and ssl_certificates (Partie 1.4.3)

Revision ID: 0027
Revises: 0026
Create Date: 2026-09-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "acme_accounts",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("directory_url", sa.String(length=500), nullable=False),
        sa.Column("account_key_pem_encrypted", sa.Text(), nullable=False),
        sa.Column("account_url", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint("uq_acme_accounts_directory_url", "acme_accounts", ["directory_url"])
    op.execute("ALTER TABLE public.acme_accounts ENABLE ROW LEVEL SECURITY")

    op.create_table(
        "ssl_certificates",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("domain", sa.String(length=255), sa.ForeignKey("custom_domains.domain", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending_dns01"),
        sa.Column("cert_pem", sa.Text(), nullable=True),
        sa.Column("key_pem_encrypted", sa.Text(), nullable=False),
        sa.Column("chain_pem", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acme_order_url", sa.String(length=500), nullable=True),
        sa.Column("acme_challenge_url", sa.String(length=500), nullable=True),
        sa.Column("dns01_record_name", sa.String(length=300), nullable=True),
        sa.Column("dns01_record_value", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint("uq_ssl_certificates_domain", "ssl_certificates", ["domain"])
    op.execute("ALTER TABLE public.ssl_certificates ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("ssl_certificates")
    op.drop_table("acme_accounts")

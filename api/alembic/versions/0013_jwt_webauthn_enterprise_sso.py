"""add jwt_signing_keys, webauthn_credentials, enterprise_sso_connections/accounts (audit Categorie 4, items 26/27/28)

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "jwt_signing_keys",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("secret", sa.String(500), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("ALTER TABLE public.jwt_signing_keys ENABLE ROW LEVEL SECURITY")

    op.create_table(
        "webauthn_credentials",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("credential_id", sa.LargeBinary(), nullable=False),
        sa.Column("public_key", sa.LargeBinary(), nullable=False),
        sa.Column("sign_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("transports", sa.String(200), nullable=True),
        sa.Column("nickname", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_webauthn_credentials_user_id", "webauthn_credentials", ["user_id"])
    op.create_index("ix_webauthn_credentials_credential_id", "webauthn_credentials", ["credential_id"], unique=True)
    op.execute("ALTER TABLE public.webauthn_credentials ENABLE ROW LEVEL SECURITY")

    op.create_table(
        "enterprise_sso_connections",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("email_domain", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("issuer", sa.String(500), nullable=False),
        sa.Column("client_id", sa.String(255), nullable=False),
        sa.Column("client_secret_encrypted", sa.String(1000), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_admin_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("email_domain", name="uq_enterprise_sso_connections_email_domain"),
    )
    op.execute("ALTER TABLE public.enterprise_sso_connections ENABLE ROW LEVEL SECURITY")

    op.create_table(
        "enterprise_sso_accounts",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "connection_id", sa.Uuid(as_uuid=True),
            sa.ForeignKey("enterprise_sso_connections.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("provider_subject", sa.String(255), nullable=False),
        sa.Column("provider_email", sa.String(320), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("connection_id", "provider_subject", name="uq_enterprise_sso_accounts_connection_subject"),
    )
    op.create_index("ix_enterprise_sso_accounts_user_id", "enterprise_sso_accounts", ["user_id"])
    op.create_index("ix_enterprise_sso_accounts_connection_id", "enterprise_sso_accounts", ["connection_id"])
    op.execute("ALTER TABLE public.enterprise_sso_accounts ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("enterprise_sso_accounts")
    op.drop_table("enterprise_sso_connections")
    op.drop_table("webauthn_credentials")
    op.drop_table("jwt_signing_keys")

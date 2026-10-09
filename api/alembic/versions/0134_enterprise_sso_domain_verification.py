"""Require proven domain ownership before an enterprise SSO connection routes logins.

Existing connections stay routable only when a superadmin created them;
every other connection must pass the DNS TXT check again.

Revision ID: 0134
Revises: 0133
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0134"
down_revision: str | None = "0133"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "enterprise_sso_connections",
        sa.Column("domain_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("enterprise_sso_connections", sa.Column("domain_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("enterprise_sso_connections", sa.Column("domain_verification_token", sa.String(length=64), nullable=True))
    op.execute(
        "UPDATE enterprise_sso_connections SET domain_verified = true, domain_verified_at = now() "
        "WHERE created_by_admin_id IN (SELECT id FROM users WHERE role = 'superadmin')"
    )
    # Pre-existing rows get a token so the owner can publish the DNS record.
    op.execute(
        "UPDATE enterprise_sso_connections SET domain_verification_token = md5(random()::text || id::text) "
        "WHERE domain_verification_token IS NULL"
    )


def downgrade() -> None:
    op.drop_column("enterprise_sso_connections", "domain_verification_token")
    op.drop_column("enterprise_sso_connections", "domain_verified_at")
    op.drop_column("enterprise_sso_connections", "domain_verified")

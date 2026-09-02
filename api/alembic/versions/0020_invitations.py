"""add invitations (Partie 1.3.4 -- email-based org invitations)

Revision ID: 0020
Revises: 0019
Create Date: 2026-09-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Reuses the existing "organizationrole" Postgres enum type (created by
# migration 0012 for organization_members.role) -- create_type=False so
# this table's own CREATE TABLE doesn't try (and fail) to CREATE TYPE a
# second time. Must be the dialect-specific postgresql.ENUM, not the
# generic sa.Enum -- verified empirically: sa.Enum(..., create_type=False)
# still attempted CREATE TYPE inside op.create_table() and failed with
# "type already exists" (some Alembic/SQLAlchemy version combinations
# don't propagate create_type through the generic wrapper in that code
# path); postgresql.ENUM(..., create_type=False) is unambiguous and
# confirmed to work.
organization_role = postgresql.ENUM(
    "owner", "admin", "manager", "member", "viewer", name="organizationrole", create_type=False,
)


def upgrade() -> None:
    op.create_table(
        "invitations",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("role", organization_role, nullable=False),
        sa.Column("invited_by", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_invitations_organization_id", "invitations", ["organization_id"])
    op.create_index("ix_invitations_email", "invitations", ["email"])
    op.create_index("ix_invitations_token_hash", "invitations", ["token_hash"], unique=True)
    op.create_unique_constraint("uq_invitations_org_email", "invitations", ["organization_id", "email"])
    op.execute("ALTER TABLE public.invitations ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("invitations")

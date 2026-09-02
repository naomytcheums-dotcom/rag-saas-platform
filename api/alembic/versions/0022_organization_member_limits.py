"""add per-member limits to organization_members (Partie 1.3.7)

Revision ID: 0022
Revises: 0021
Create Date: 2026-09-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("organization_members", sa.Column("daily_request_limit", sa.Integer(), nullable=True))
    op.add_column("organization_members", sa.Column("max_documents", sa.Integer(), nullable=True))
    op.add_column("organization_members", sa.Column("max_conversations", sa.Integer(), nullable=True))
    op.add_column(
        "organization_members",
        sa.Column("can_create_workspaces", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "organization_members",
        sa.Column("can_create_teams", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "organization_members",
        sa.Column("can_invite_members", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("organization_members", "can_invite_members")
    op.drop_column("organization_members", "can_create_teams")
    op.drop_column("organization_members", "can_create_workspaces")
    op.drop_column("organization_members", "max_conversations")
    op.drop_column("organization_members", "max_documents")
    op.drop_column("organization_members", "daily_request_limit")

"""add teams and team_members (Partie 1.3.3)

Revision ID: 0018
Revises: 0017
Create Date: 2026-09-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

team_role = sa.Enum("admin", "member", name="teamrole")


def upgrade() -> None:
    op.create_table(
        "teams",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_teams_organization_id", "teams", ["organization_id"])
    op.execute("ALTER TABLE public.teams ENABLE ROW LEVEL SECURITY")

    op.create_table(
        "team_members",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("team_id", sa.Uuid(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", team_role, nullable=False, server_default="member"),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_team_members_team_id", "team_members", ["team_id"])
    op.create_index("ix_team_members_user_id", "team_members", ["user_id"])
    op.create_unique_constraint("uq_team_members_team_user", "team_members", ["team_id", "user_id"])
    op.execute("ALTER TABLE public.team_members ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("team_members")
    op.drop_table("teams")
    team_role.drop(op.get_bind(), checkfirst=True)

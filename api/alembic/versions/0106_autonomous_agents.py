"""Partie 23 -- autonomous agents. See api/models/autonomous_agent.py's
own module docstring for why this is a genuinely new, separate entity
(goal-driven, self-planning) rather than columns bolted onto the
existing Partie 5.3 `Agent` (a configured, multi-turn chatbot persona).

Revision ID: 0106
Revises: 0105
Create Date: 2026-09-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0106"
down_revision: Union[str, None] = "0105"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "autonomous_agents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="idle"),
        sa.Column("max_steps", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tools_enabled", sa.JSON(), nullable=False),
        sa.Column("guardrails", sa.JSON(), nullable=False),
        sa.Column("memory_config", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_autonomous_agents_organization_id", "autonomous_agents", ["organization_id"])
    op.execute("ALTER TABLE public.autonomous_agents ENABLE ROW LEVEL SECURITY")

    op.create_table(
        "agent_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["autonomous_agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_plans_agent_id", "agent_plans", ["agent_id"])
    op.execute("ALTER TABLE public.agent_plans ENABLE ROW LEVEL SECURITY")

    op.create_table(
        "agent_steps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["plan_id"], ["agent_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_steps_plan_id", "agent_steps", ["plan_id"])
    op.execute("ALTER TABLE public.agent_steps ENABLE ROW LEVEL SECURITY")

    op.create_table(
        "agent_memories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("memory_type", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("importance", sa.Numeric(3, 2), nullable=False, server_default="0.5"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["autonomous_agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_memories_agent_id", "agent_memories", ["agent_id"])
    op.execute("ALTER TABLE public.agent_memories ENABLE ROW LEVEL SECURITY")

    op.create_table(
        "agent_collaborations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("initiator_agent_id", sa.Uuid(), nullable=False),
        sa.Column("collaborator_agent_id", sa.Uuid(), nullable=False),
        sa.Column("task", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["initiator_agent_id"], ["autonomous_agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["collaborator_agent_id"], ["autonomous_agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_collaborations_initiator_agent_id", "agent_collaborations", ["initiator_agent_id"])
    op.create_index("ix_agent_collaborations_collaborator_agent_id", "agent_collaborations", ["collaborator_agent_id"])
    op.execute("ALTER TABLE public.agent_collaborations ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("agent_collaborations")
    op.drop_table("agent_memories")
    op.drop_table("agent_steps")
    op.drop_table("agent_plans")
    op.drop_table("autonomous_agents")

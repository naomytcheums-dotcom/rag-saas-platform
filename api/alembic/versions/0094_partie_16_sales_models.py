"""Partie 16 (bis) -- sales models: Subscription.trial_ends_at,
licenses, support_tickets, support_ticket_responses, resellers,
sub_clients.

Revision ID: 0094
Revises: 0093
Create Date: 2026-09-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0094"
down_revision: Union[str, None] = "0093"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("subscriptions", sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True))

    license_status = sa.Enum("active", "expired", "revoked", name="licensestatus")
    ticket_priority = sa.Enum("critical", "high", "normal", "low", name="ticketpriority")
    ticket_status = sa.Enum("open", "in_progress", "resolved", "closed", name="ticketstatus")

    op.create_table(
        "licenses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("key", sa.String(64), nullable=False, unique=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("plan_key", sa.String(50), nullable=False),
        sa.Column("status", license_status, nullable=False, server_default="active"),
        sa.Column("max_activations", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("activation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "support_tickets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("priority", ticket_priority, nullable=False, server_default="normal"),
        sa.Column("status", ticket_status, nullable=False, server_default="open"),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("first_responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_support_tickets_organization_id", "support_tickets", ["organization_id"])
    op.create_index("ix_support_tickets_created_at", "support_tickets", ["created_at"])

    op.create_table(
        "support_ticket_responses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_staff", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_support_ticket_responses_ticket_id", "support_ticket_responses", ["ticket_id"])

    op.create_table(
        "resellers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("commission_percent", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "sub_clients",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("reseller_id", sa.Uuid(), sa.ForeignKey("resellers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_sub_clients_reseller_id", "sub_clients", ["reseller_id"])


def downgrade() -> None:
    op.drop_table("sub_clients")
    op.drop_table("resellers")
    op.drop_table("support_ticket_responses")
    op.drop_table("support_tickets")
    sa.Enum(name="ticketstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="ticketpriority").drop(op.get_bind(), checkfirst=True)
    op.drop_table("licenses")
    sa.Enum(name="licensestatus").drop(op.get_bind(), checkfirst=True)
    op.drop_column("subscriptions", "trial_ends_at")

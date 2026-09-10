"""Real Twilio SMS/WhatsApp send log.

Revision ID: 0093
Revises: 0092
Create Date: 2026-09-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0093"
down_revision: Union[str, None] = "0092"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    channel_type = sa.Enum("sms", "whatsapp", name="smschannel")
    status_type = sa.Enum("queued", "sent", "failed", name="smsstatus")

    op.create_table(
        "sms_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", channel_type, nullable=False),
        sa.Column("to_number", sa.String(32), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", status_type, nullable=False, server_default="queued"),
        sa.Column("provider_message_id", sa.String(64), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_sms_messages_organization_id", "sms_messages", ["organization_id"])
    op.create_index("ix_sms_messages_created_at", "sms_messages", ["created_at"])


def downgrade() -> None:
    op.drop_table("sms_messages")
    sa.Enum(name="smsstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="smschannel").drop(op.get_bind(), checkfirst=True)

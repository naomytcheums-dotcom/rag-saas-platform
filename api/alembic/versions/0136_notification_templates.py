"""Create `notification_templates` (TEN-006).

The NotificationTemplate model (api/models/notification_template.py) and its CRUD routes existed, but no migration ever created the table:
on a database built by `alembic upgrade head`, GET/POST /organizations/{id}/notifications/templates* answered 500 ("relation does not
exist"). Additive and reversible (downgrade drops the table). Row level security is enabled like on every other table since 0131.

Revision ID: 0136
Revises: 0135
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0136"
down_revision: str | None = "0135"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_templates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("notification_type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("email_subject", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "notification_type", name="uq_notification_template_org_type"),
    )
    op.create_index("ix_notification_templates_organization_id", "notification_templates", ["organization_id"])
    op.create_index("ix_notification_templates_notification_type", "notification_templates", ["notification_type"])
    op.execute("ALTER TABLE notification_templates ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("notification_templates")

"""Partie 12 -- billing: plan pricing/feature/Stripe columns,
subscription billing_period/stripe_subscription_id, credits,
credit_transactions, invoices, invoice_lines, stripe_customers,
stripe_events, usage_alerts.

Revision ID: 0090
Revises: 0089
Create Date: 2026-09-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0090"
down_revision: Union[str, None] = "0089"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("plans", sa.Column("yearly_price_cents", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("plans", sa.Column("max_api_keys", sa.Integer(), nullable=True))
    op.add_column("plans", sa.Column("max_webhooks", sa.Integer(), nullable=True))
    op.add_column("plans", sa.Column("max_requests_per_month", sa.Integer(), nullable=True))
    op.add_column("plans", sa.Column("priority_support", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("plans", sa.Column("advanced_features", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("plans", sa.Column("sla", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("plans", sa.Column("stripe_product_id", sa.String(100), nullable=True))
    op.add_column("plans", sa.Column("stripe_price_id_monthly", sa.String(100), nullable=True))
    op.add_column("plans", sa.Column("stripe_price_id_yearly", sa.String(100), nullable=True))

    op.add_column("subscriptions", sa.Column("billing_period", sa.String(10), nullable=False, server_default="monthly"))
    op.add_column("subscriptions", sa.Column("stripe_subscription_id", sa.String(100), nullable=True))

    credit_txn_type = sa.Enum("purchase", "consume", "refund", "grant", name="credittransactiontype")
    invoice_status = sa.Enum("draft", "pending", "sent", "paid", "overdue", "void", "refunded", name="invoicestatus")

    op.create_table(
        "credits",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("balance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "credit_transactions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", credit_txn_type, nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(200), nullable=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_credit_transactions_organization_id", "credit_transactions", ["organization_id"])
    op.create_index("ix_credit_transactions_created_at", "credit_transactions", ["created_at"])

    op.create_table(
        "invoices",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("number", sa.String(40), nullable=False, unique=True),
        sa.Column("status", invoice_status, nullable=False, server_default="draft"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("subtotal_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("vat_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("void_reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_invoices_organization_id", "invoices", ["organization_id"])
    op.create_index("ix_invoices_created_at", "invoices", ["created_at"])

    op.create_table(
        "invoice_lines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("invoice_id", sa.Uuid(), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit_price_cents", sa.Integer(), nullable=False),
        sa.Column("total_cents", sa.Integer(), nullable=False),
    )
    op.create_index("ix_invoice_lines_invoice_id", "invoice_lines", ["invoice_id"])

    op.create_table(
        "stripe_customers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("stripe_customer_id", sa.String(100), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "stripe_events",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("type", sa.String(100), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("payload_summary", sa.Text(), nullable=True),
    )

    op.create_table(
        "usage_alerts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("threshold_percent", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "resource_type", "threshold_percent", name="uq_usage_alert_org_metric_threshold"),
    )
    op.create_index("ix_usage_alerts_organization_id", "usage_alerts", ["organization_id"])


def downgrade() -> None:
    op.drop_table("usage_alerts")
    op.drop_table("stripe_events")
    op.drop_table("stripe_customers")
    op.drop_table("invoice_lines")
    op.drop_table("invoices")
    sa.Enum(name="invoicestatus").drop(op.get_bind(), checkfirst=True)
    op.drop_table("credit_transactions")
    op.drop_table("credits")
    sa.Enum(name="credittransactiontype").drop(op.get_bind(), checkfirst=True)

    op.drop_column("subscriptions", "stripe_subscription_id")
    op.drop_column("subscriptions", "billing_period")

    op.drop_column("plans", "stripe_price_id_yearly")
    op.drop_column("plans", "stripe_price_id_monthly")
    op.drop_column("plans", "stripe_product_id")
    op.drop_column("plans", "sla")
    op.drop_column("plans", "advanced_features")
    op.drop_column("plans", "priority_support")
    op.drop_column("plans", "max_requests_per_month")
    op.drop_column("plans", "max_webhooks")
    op.drop_column("plans", "max_api_keys")
    op.drop_column("plans", "yearly_price_cents")

"""Phase 5, Étape 2 -- Paystack + Stripe multi-provider billing.

Three real, additive-and-safe changes:

1. `organizations.billing_country` -- nullable ISO 3166-1 alpha-2 code,
   used only to auto-select a billing provider. NULL for every existing
   row (no backfill possible -- we don't know an existing org's
   country), which resolves to Stripe, the exact same provider every
   existing organization already uses today.
2. `plans.paystack_plan_code_monthly` / `paystack_plan_code_yearly` --
   nullable, Paystack's own equivalent of the existing
   `stripe_price_id_monthly/yearly` columns. NULL until an operator
   actually syncs real Paystack plans.
   `subscriptions.paystack_subscription_code` -- nullable, Paystack's
   own equivalent of the existing `stripe_subscription_id` column.
3. Renames `stripe_customers` -> `payment_customers` and
   `stripe_events` -> `payment_events`, adding a `provider` column to
   each (backfilled to 'stripe' on every pre-existing row -- the exact
   provider those rows were always for) and re-scoping their unique
   constraints per-provider instead of globally. See
   api/models/billing.py's own docstring for why this couldn't stay a
   Stripe-only table once a second provider exists.

Reversible: `downgrade` renames the tables back, drops the `provider`
column and the two new plan columns and the org column. Renaming back
is safe only if no Paystack rows were written in between (a real
constraint of any additive-schema rollback after real usage) --
documented here rather than silently pretended away.

Revision ID: 0115
Revises: 0114
Create Date: 2026-09-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0115"
down_revision: Union[str, None] = "0114"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PROVIDER_ENUM = sa.Enum("stripe", "paystack", name="paymentprovider")


def upgrade() -> None:
    op.add_column("organizations", sa.Column("billing_country", sa.String(length=2), nullable=True))
    op.add_column("plans", sa.Column("paystack_plan_code_monthly", sa.String(length=100), nullable=True))
    op.add_column("plans", sa.Column("paystack_plan_code_yearly", sa.String(length=100), nullable=True))
    op.add_column("subscriptions", sa.Column("paystack_subscription_code", sa.String(length=100), nullable=True))

    op.rename_table("stripe_customers", "payment_customers")
    _PROVIDER_ENUM.create(op.get_bind(), checkfirst=True)
    op.add_column("payment_customers", sa.Column("provider", _PROVIDER_ENUM, nullable=False, server_default="stripe"))
    op.alter_column("payment_customers", "provider", server_default=None)
    op.alter_column("payment_customers", "stripe_customer_id", new_column_name="external_customer_id")
    op.drop_constraint("stripe_customers_organization_id_key", "payment_customers", type_="unique")
    op.drop_constraint("stripe_customers_stripe_customer_id_key", "payment_customers", type_="unique")
    op.create_unique_constraint("uq_payment_customer_org_provider", "payment_customers", ["organization_id", "provider"])
    op.create_unique_constraint("uq_payment_customer_provider_external_id", "payment_customers", ["provider", "external_customer_id"])

    op.rename_table("stripe_events", "payment_events")
    op.add_column("payment_events", sa.Column("provider", _PROVIDER_ENUM, nullable=False, server_default="stripe"))
    op.alter_column("payment_events", "provider", server_default=None)
    op.drop_constraint("stripe_events_pkey", "payment_events", type_="primary")
    op.create_primary_key("payment_events_pkey", "payment_events", ["provider", "id"])


def downgrade() -> None:
    op.drop_constraint("payment_events_pkey", "payment_events", type_="primary")
    op.create_primary_key("stripe_events_pkey", "payment_events", ["id"])
    op.drop_column("payment_events", "provider")
    op.rename_table("payment_events", "stripe_events")

    op.drop_constraint("uq_payment_customer_provider_external_id", "payment_customers", type_="unique")
    op.drop_constraint("uq_payment_customer_org_provider", "payment_customers", type_="unique")
    op.alter_column("payment_customers", "external_customer_id", new_column_name="stripe_customer_id")
    op.drop_column("payment_customers", "provider")
    _PROVIDER_ENUM.drop(op.get_bind(), checkfirst=True)
    op.rename_table("payment_customers", "stripe_customers")
    op.create_unique_constraint("stripe_customers_organization_id_key", "stripe_customers", ["organization_id"])
    op.create_unique_constraint("stripe_customers_stripe_customer_id_key", "stripe_customers", ["stripe_customer_id"])

    op.drop_column("subscriptions", "paystack_subscription_code")
    op.drop_column("plans", "paystack_plan_code_yearly")
    op.drop_column("plans", "paystack_plan_code_monthly")
    op.drop_column("organizations", "billing_country")

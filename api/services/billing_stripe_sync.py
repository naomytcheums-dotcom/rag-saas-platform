"""Partie 12.2 -- sync this deployment's real Plan rows to real Stripe
Products/Prices. Like every other function in api/services/billing_stripe.py,
raises StripeNotConfiguredError until a real STRIPE_SECRET_KEY exists."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.admin import Plan
from api.services.billing_stripe import _client


async def create_stripe_product(plan: Plan):
    stripe = _client()
    return stripe.Product.create(name=plan.name, metadata={"plan_key": plan.key})


async def create_stripe_price(product_id: str, amount_cents: int, interval: str):
    stripe = _client()
    return stripe.Price.create(product=product_id, unit_amount=amount_cents, currency="eur", recurring={"interval": interval})


async def sync_stripe_products(db: AsyncSession) -> int:
    _client()  # raises StripeNotConfiguredError early if unset
    plans = list((await db.scalars(select(Plan).where(Plan.is_active.is_(True)))).all())
    synced = 0
    for plan in plans:
        if plan.monthly_price_cents <= 0:
            continue  # no real Stripe product needed for a free plan
        if not plan.stripe_product_id:
            product = await create_stripe_product(plan)
            plan.stripe_product_id = product["id"]
        synced += 1
    await db.flush()
    return synced


async def sync_stripe_prices(db: AsyncSession) -> int:
    _client()
    plans = list((await db.scalars(select(Plan).where(Plan.stripe_product_id.is_not(None)))).all())
    synced = 0
    for plan in plans:
        if not plan.stripe_price_id_monthly and plan.monthly_price_cents > 0:
            price = await create_stripe_price(plan.stripe_product_id, plan.monthly_price_cents, "month")
            plan.stripe_price_id_monthly = price["id"]
            synced += 1
        if not plan.stripe_price_id_yearly and plan.yearly_price_cents > 0:
            price = await create_stripe_price(plan.stripe_product_id, plan.yearly_price_cents, "year")
            plan.stripe_price_id_yearly = price["id"]
            synced += 1
    await db.flush()
    return synced

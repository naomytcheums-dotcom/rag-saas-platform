"""
Partie 12.2 -- real Stripe integration code, honestly scoped: this
environment has no real Stripe account/keys (settings.STRIPE_SECRET_KEY
is None by default, see api/config.py), so every function below checks
that first and raises StripeNotConfiguredError rather than pretending
to reach a payment processor that isn't there -- same honest-501
pattern api/services/admin_subscriptions.py already established for
POST /admin/subscriptions/{id}/refund. The moment a real key is set in
.env, every function here makes a real Stripe API call -- nothing is
mocked internally.

**Phase 5, Étape 2**: these module-level functions are kept exactly as
they were (still called directly by the pre-existing `/organizations/
{org_id}/billing/stripe/...` endpoints, still using the exact same
`StripeNotConfiguredError`) -- nothing here was removed. What changed
is only the storage layer: `StripeCustomer`/`StripeEvent` were renamed
to the provider-generic `PaymentCustomer`/`PaymentEvent`
(api/models/billing.py), so every query/insert below now also filters/
sets `provider=PaymentProvider.stripe`. `StripeProvider` at the bottom
of this module is the new, thin `BillingProvider` adapter Étape 2's own
registry (api/services/billing_providers/registry.py) actually uses --
it just calls the same functions above, so there is exactly one real
Stripe implementation, not two.
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.admin import Plan, Subscription, SubscriptionStatus
from api.models.billing import PaymentCustomer, PaymentProvider
from api.models.organization import Organization
from api.services.billing_providers.base import ProviderNotConfiguredError, claim_payment_event

logger = logging.getLogger(__name__)


class StripeNotConfiguredError(ProviderNotConfiguredError):
    """Kept as its own subclass (not just an alias) so the pre-existing
    `/organizations/{org_id}/billing/stripe/...` endpoints' own
    `except billing_stripe.StripeNotConfiguredError` clauses keep
    working unchanged, while new, provider-generic code
    (api/services/billing_providers/, the router's new `/checkout` etc.
    endpoints) can catch the shared `ProviderNotConfiguredError` base
    instead and work identically for either provider."""


class StripePaymentMethodNotFoundError(Exception):
    """The requested method is not attached to the organization's Stripe customer."""


def _client():
    if not settings.STRIPE_SECRET_KEY:
        raise StripeNotConfiguredError(
            "Stripe is not configured on this deployment -- set STRIPE_SECRET_KEY in .env to enable real payments."
        )
    import stripe

    stripe.api_key = settings.STRIPE_SECRET_KEY
    stripe.api_version = settings.STRIPE_API_VERSION
    return stripe


async def get_stripe_customer(db: AsyncSession, organization_id: uuid.UUID) -> PaymentCustomer | None:
    return await db.scalar(
        select(PaymentCustomer).where(PaymentCustomer.organization_id == organization_id, PaymentCustomer.provider == PaymentProvider.stripe)
    )


async def create_stripe_customer(db: AsyncSession, organization_id: uuid.UUID, *, email: str, name: str) -> PaymentCustomer:
    existing = await get_stripe_customer(db, organization_id)
    if existing is not None:
        return existing

    stripe = _client()
    customer = stripe.Customer.create(email=email, name=name, metadata={"organization_id": str(organization_id)})
    row = PaymentCustomer(organization_id=organization_id, provider=PaymentProvider.stripe, external_customer_id=customer["id"])
    db.add(row)
    await db.flush()
    return row


async def create_checkout_session(db: AsyncSession, organization_id: uuid.UUID, *, price_id: str, email: str, org_name: str) -> str:
    stripe = _client()
    customer = await create_stripe_customer(db, organization_id, email=email, name=org_name)
    session = stripe.checkout.Session.create(
        customer=customer.external_customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=settings.STRIPE_SUCCESS_URL,
        cancel_url=settings.STRIPE_CANCEL_URL,
        metadata={"organization_id": str(organization_id)},
    )
    return session["url"]


async def create_credit_pack_checkout_session(db: AsyncSession, organization_id: uuid.UUID, *, pack: dict, email: str, org_name: str) -> str:
    """Hardening Mission (§23) -- a ONE-OFF (`mode="payment"`) Stripe Checkout for a fixed credit pack. The pack
    and organization travel in the session's metadata, set server-side here (a buyer cannot alter them), and the
    credits are granted ONLY when Stripe's `checkout.session.completed` webhook reports it paid
    (`handle_stripe_webhook`) -- never on the redirect back, which a user can forge or skip."""
    stripe = _client()
    customer = await create_stripe_customer(db, organization_id, email=email, name=org_name)
    session = stripe.checkout.Session.create(
        customer=customer.external_customer_id,
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": settings.CREDIT_PACK_CURRENCY,
                "unit_amount": pack["price_cents"],
                "product_data": {"name": f"{pack['name']} credit pack ({pack['credits']:,} credits)"},
            },
            "quantity": 1,
        }],
        success_url=settings.STRIPE_SUCCESS_URL,
        cancel_url=settings.STRIPE_CANCEL_URL,
        metadata={"organization_id": str(organization_id), "kind": "credit_pack", "pack_id": pack["id"]},
    )
    return session["url"]


async def create_portal_session(db: AsyncSession, organization_id: uuid.UUID) -> str:
    stripe = _client()
    customer = await get_stripe_customer(db, organization_id)
    if customer is None:
        raise StripeNotConfiguredError("This organization has no Stripe customer yet -- start a checkout session first.")
    session = stripe.billing_portal.Session.create(customer=customer.external_customer_id, return_url=settings.STRIPE_PORTAL_RETURN_URL)
    return session["url"]


async def list_payment_methods(db: AsyncSession, organization_id: uuid.UUID) -> list[dict]:
    stripe = _client()
    customer = await get_stripe_customer(db, organization_id)
    if customer is None:
        return []
    methods = stripe.PaymentMethod.list(customer=customer.external_customer_id, type="card")
    return [
        {"id": m["id"], "brand": m["card"]["brand"], "last4": m["card"]["last4"], "exp_month": m["card"]["exp_month"], "exp_year": m["card"]["exp_year"]}
        for m in methods["data"]
    ]


async def detach_payment_method(db: AsyncSession, organization_id: uuid.UUID, payment_method_id: str) -> None:
    stripe = _client()
    customer = await get_stripe_customer(db, organization_id)
    if customer is None:
        raise StripePaymentMethodNotFoundError("Payment method not found")
    methods = stripe.PaymentMethod.list(customer=customer.external_customer_id, type="card")
    if not any(method["id"] == payment_method_id for method in methods["data"]):
        raise StripePaymentMethodNotFoundError("Payment method not found")
    stripe.PaymentMethod.detach(payment_method_id)


async def cancel_stripe_subscription(db: AsyncSession, organization_id: uuid.UUID, *, at_period_end: bool = True) -> None:
    stripe = _client()
    sub = await db.scalar(select(Subscription).where(Subscription.organization_id == organization_id))
    if sub is None or not sub.stripe_subscription_id:
        raise StripeNotConfiguredError("This organization has no real Stripe subscription to cancel.")
    if at_period_end:
        stripe.Subscription.modify(sub.stripe_subscription_id, cancel_at_period_end=True)
    else:
        stripe.Subscription.cancel(sub.stripe_subscription_id)


async def list_stripe_invoices(db: AsyncSession, organization_id: uuid.UUID) -> list[dict]:
    stripe = _client()
    customer = await get_stripe_customer(db, organization_id)
    if customer is None:
        return []
    invoices = stripe.Invoice.list(customer=customer.external_customer_id, limit=25)
    return [{"id": i["id"], "number": i.get("number"), "status": i["status"], "total": i["total"], "currency": i["currency"], "hosted_invoice_url": i.get("hosted_invoice_url")} for i in invoices["data"]]


def verify_webhook_signature(payload: bytes, signature_header: str):
    stripe = _client()
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise StripeNotConfiguredError("STRIPE_WEBHOOK_SECRET is not set -- cannot verify webhook authenticity.")
    return stripe.Webhook.construct_event(payload, signature_header, settings.STRIPE_WEBHOOK_SECRET)


async def handle_stripe_webhook(db: AsyncSession, event: dict) -> bool:
    """Real event processing, idempotent via PaymentEvent (Stripe
    guarantees at-least-once delivery, never exactly-once). Returns
    False if this event id was already applied.

    Hardening Mission (§5, webhook anti-replay) -- the event id is
    claimed atomically FIRST (`claim_payment_event`), before any side
    effect runs, closing a real race window where two concurrent
    deliveries of the same event could both pass a plain existence
    check and both apply their side effects."""
    event_id = event["id"]
    event_type = event["type"]
    data = event["data"]["object"]

    if not await claim_payment_event(db, PaymentProvider.stripe, event_id, event_type, str(data.get("id", ""))):
        return False

    if event_type == "checkout.session.completed" and (data.get("metadata") or {}).get("kind") == "credit_pack":
        await _grant_paid_credit_pack(db, data)
    elif event_type in ("customer.subscription.created", "customer.subscription.updated"):
        org_id = data.get("metadata", {}).get("organization_id")
        if org_id:
            sub = await db.scalar(select(Subscription).where(Subscription.organization_id == uuid.UUID(org_id)))
            if sub is not None:
                sub.status = SubscriptionStatus.active if data["status"] == "active" else SubscriptionStatus.past_due
                await db.flush()
    elif event_type == "customer.subscription.deleted":
        org_id = data.get("metadata", {}).get("organization_id")
        if org_id:
            sub = await db.scalar(select(Subscription).where(Subscription.organization_id == uuid.UUID(org_id)))
            if sub is not None:
                sub.status = SubscriptionStatus.canceled
                await db.flush()
    elif event_type == "invoice.payment_failed":
        org_id = data.get("metadata", {}).get("organization_id")
        if org_id:
            sub = await db.scalar(select(Subscription).where(Subscription.organization_id == uuid.UUID(org_id)))
            if sub is not None:
                sub.status = SubscriptionStatus.past_due
                await db.flush()
                from api.services.notifications import notify_billing_payment_failed

                await notify_billing_payment_failed(db, uuid.UUID(org_id))
    elif event_type in ("payment_intent.succeeded", "charge.succeeded", "invoice.paid"):
        # Real, additive: the real "a payment succeeded" events. Each
        # carries the org_id differently, so we read it from every real
        # place Stripe actually puts it (metadata first, then the
        # nested invoice/subscription metadata), then notify + mark
        # any real past_due subscription active again. Real no-op when
        # no real org_id can be found (e.g. a one-off charge).
        org_id = (
            data.get("metadata", {}).get("organization_id")
            or (data.get("invoice") or {}).get("metadata", {}).get("organization_id")
            or (data.get("subscription_details") or {}).get("metadata", {}).get("organization_id")
        )
        if org_id:
            sub = await db.scalar(select(Subscription).where(Subscription.organization_id == uuid.UUID(org_id)))
            if sub is not None and sub.status == SubscriptionStatus.past_due:
                sub.status = SubscriptionStatus.active
                await db.flush()
            from api.services.notifications import notify_billing_payment_succeeded

            await notify_billing_payment_succeeded(db, uuid.UUID(org_id))

    return True


async def _grant_paid_credit_pack(db: AsyncSession, session: dict) -> None:
    """Grants the credits of a PAID credit-pack checkout. Defensive on purpose: anything that does not
    match what `create_credit_pack_checkout_session` created (unpaid, unknown pack, amount not the pack's price,
    malformed organization id) grants NOTHING and is logged. Idempotency is the event-id claim made by the caller
    (`claim_payment_event`), so a re-delivered event cannot grant twice."""
    from api.security.credit_packs import get_credit_pack
    from api.services.billing_credits import add_credits

    metadata = session.get("metadata") or {}
    pack = get_credit_pack(metadata.get("pack_id", ""))
    if session.get("payment_status") != "paid":
        logger.warning("credit pack checkout %s not paid (%s): nothing granted", session.get("id"), session.get("payment_status"))
        return
    if pack is None or session.get("amount_total") != pack["price_cents"]:
        logger.error("credit pack checkout %s does not match a known pack/price (pack=%s, amount=%s): nothing granted", session.get("id"), metadata.get("pack_id"), session.get("amount_total"))
        return
    try:
        organization_id = uuid.UUID(metadata.get("organization_id", ""))
    except ValueError:
        logger.error("credit pack checkout %s has no valid organization id: nothing granted", session.get("id"))
        return
    await add_credits(db, organization_id, pack["credits"], source=f"Stripe checkout {session.get('id')} ({pack['name']} pack)")


class StripeProvider:
    """Thin `BillingProvider` adapter over the module-level functions
    above -- see this module's own docstring for why this doesn't
    duplicate the Stripe logic. Registered as `PaymentProvider.stripe`
    in api/services/billing_providers/registry.py."""

    name = "stripe"

    def is_configured(self) -> bool:
        return bool(settings.STRIPE_SECRET_KEY)

    async def create_checkout_session(self, db: AsyncSession, organization_id: uuid.UUID, *, plan: Plan, billing_period: str, email: str, org_name: str) -> str:
        price_id = plan.stripe_price_id_yearly if billing_period == "yearly" else plan.stripe_price_id_monthly
        if not price_id:
            raise ValueError(f"Plan {plan.key!r} has no stripe_price_id_{billing_period} set -- sync it first (api/services/billing_stripe_sync.py).")
        return await create_checkout_session(db, organization_id, price_id=price_id, email=email, org_name=org_name)

    async def create_credit_pack_checkout(self, db: AsyncSession, organization_id: uuid.UUID, *, pack: dict, email: str, org_name: str) -> str:
        return await create_credit_pack_checkout_session(db, organization_id, pack=pack, email=email, org_name=org_name)

    async def create_portal_session(self, db: AsyncSession, organization_id: uuid.UUID) -> str:
        return await create_portal_session(db, organization_id)

    async def list_payment_methods(self, db: AsyncSession, organization_id: uuid.UUID) -> list[dict]:
        return await list_payment_methods(db, organization_id)

    async def cancel_subscription(self, db: AsyncSession, organization_id: uuid.UUID, *, at_period_end: bool = True) -> None:
        await cancel_stripe_subscription(db, organization_id, at_period_end=at_period_end)

    async def list_provider_invoices(self, db: AsyncSession, organization_id: uuid.UUID) -> list[dict]:
        return await list_stripe_invoices(db, organization_id)

    def verify_webhook_signature(self, payload: bytes, signature_header: str) -> dict:
        return dict(verify_webhook_signature(payload, signature_header))

    async def handle_webhook(self, db: AsyncSession, event: dict) -> bool:
        return await handle_stripe_webhook(db, event)

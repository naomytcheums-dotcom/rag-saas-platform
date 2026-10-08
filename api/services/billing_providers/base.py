"""Phase 5, Étape 2 -- the `BillingProvider` interface both real
providers implement. An abstract base class, not a Protocol, because
callers (the router) need a real, importable exception hierarchy
(`ProviderNotConfiguredError`) shared by both implementations -- a
router that catches one exception type must work identically whether
the resolved provider is Stripe or Paystack.
"""

from __future__ import annotations

import abc
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.admin import Plan


class ProviderNotConfiguredError(Exception):
    """Raised by any provider method when its required secret key(s)
    are not set in .env -- the same honest-501 pattern this codebase's
    Stripe code already established (api/services/billing_stripe.py),
    now shared by both providers so the router needs only one except
    clause regardless of which provider was resolved."""


async def claim_payment_event(db: AsyncSession, provider, event_id: str, event_type: str, payload_summary: str) -> bool:
    """Hardening Mission (webhook anti-replay, §5) -- closes a real race
    condition: both `billing_stripe.handle_stripe_webhook` and
    `billing_paystack.handle_paystack_webhook` used to check
    `db.get(PaymentEvent, ...)` for an existing row, apply side effects
    (subscription status changes, notifications), and only insert the
    `PaymentEvent` row afterward. Two concurrent deliveries of the same
    real event (Stripe/Paystack both retry on slow responses, and
    nothing prevents the provider from sending the same event twice in
    parallel) could both pass the initial check before either commits,
    and both apply their side effects -- a real double-notification /
    double-reconciliation bug, not a hypothetical one.

    This claims the event id FIRST, inside its own real sub-transaction
    (`SAVEPOINT` via `begin_nested`), relying on `payment_events`'s own
    composite primary key (`provider`, `id`) as the real uniqueness
    constraint the database enforces. Only the caller that wins this
    real INSERT proceeds to apply side effects; a loser returns False
    immediately, before touching any business state. If the winner's
    own side effects later raise, the outer request transaction never
    commits (the router only commits after a handler returns
    successfully), so the claim itself rolls back too -- a genuine
    provider retry after a transient failure can still reprocess the
    event, exactly like before this fix.
    """
    try:
        async with db.begin_nested():
            from api.models.billing import PaymentEvent

            db.add(PaymentEvent(provider=provider, id=event_id, type=event_type, payload_summary=payload_summary))
            await db.flush()
        return True
    except IntegrityError:
        return False


class BillingProvider(abc.ABC):
    """One instance per request, stateless beyond its own name --
    real API calls go out through each provider's own SDK/HTTP client,
    never held here."""

    name: str

    @abc.abstractmethod
    def is_configured(self) -> bool:
        """True only if this provider's real secret key is set in
        .env. Never true by default -- matches this codebase's existing
        "no real payment processor until a real key is set" honesty."""

    @abc.abstractmethod
    async def create_checkout_session(
        self, db: AsyncSession, organization_id: uuid.UUID, *, plan: Plan, billing_period: str, email: str, org_name: str
    ) -> str:
        """Returns a real, provider-hosted checkout URL. Raises
        ProviderNotConfiguredError if unconfigured, ValueError if this
        Plan has no price/plan-code set for this provider+period."""

    async def create_credit_pack_checkout(self, db: AsyncSession, organization_id: uuid.UUID, *, pack: dict, email: str, org_name: str) -> str:
        """Returns a hosted checkout URL that, once PAID, makes the provider's webhook
        grant `pack["credits"]` to the organization. Not abstract: a provider that cannot
        sell credit packs honestly says so (`NotImplementedError`) instead of every
        subclass having to fake it."""
        raise NotImplementedError(f"{self.name} does not support credit pack purchases yet")

    @abc.abstractmethod
    async def create_portal_session(self, db: AsyncSession, organization_id: uuid.UUID) -> str:
        """Returns a real, provider-hosted self-service subscription
        management URL (Stripe's Billing Portal; Paystack's own
        "manage subscription" link, api/services/billing_paystack.py's
        own docstring explains the real API this maps to)."""

    @abc.abstractmethod
    async def list_payment_methods(self, db: AsyncSession, organization_id: uuid.UUID) -> list[dict]:
        ...

    @abc.abstractmethod
    async def cancel_subscription(self, db: AsyncSession, organization_id: uuid.UUID, *, at_period_end: bool = True) -> None:
        ...

    @abc.abstractmethod
    async def list_provider_invoices(self, db: AsyncSession, organization_id: uuid.UUID) -> list[dict]:
        ...

    @abc.abstractmethod
    def verify_webhook_signature(self, payload: bytes, signature_header: str) -> dict:
        """Returns the verified, parsed event dict. Raises
        ProviderNotConfiguredError if no webhook secret is set, raises
        any other exception on a genuinely invalid signature -- callers
        must treat both as "reject the webhook", but only the first as
        "not configured" for the response status code."""

    @abc.abstractmethod
    async def handle_webhook(self, db: AsyncSession, event: dict) -> bool:
        """Applies a verified event, idempotently. Returns False if
        this exact (provider, event id) was already applied."""

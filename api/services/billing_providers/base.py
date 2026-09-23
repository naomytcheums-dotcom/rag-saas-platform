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

from sqlalchemy.ext.asyncio import AsyncSession

from api.models.admin import Plan


class ProviderNotConfiguredError(Exception):
    """Raised by any provider method when its required secret key(s)
    are not set in .env -- the same honest-501 pattern this codebase's
    Stripe code already established (api/services/billing_stripe.py),
    now shared by both providers so the router needs only one except
    clause regardless of which provider was resolved."""


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

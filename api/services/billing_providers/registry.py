"""Phase 5, Étape 2 -- the one place that decides which real billing
provider (Stripe or Paystack) a given organization's checkout/portal/
cancel/invoices calls actually go through.

Resolution order, matching this étape's own "add keys to .env later
and it works, zero code changes" requirement:
1. `organization.billing_country` in `settings.PAYSTACK_COUNTRIES`
   (default "NG,GH,ZA,KE") -> Paystack, if Paystack is configured.
2. Otherwise -> `settings.DEFAULT_BILLING_PROVIDER` (default "stripe").
3. If the resolved provider isn't actually configured (no secret key
   set), `ProviderNotConfiguredError` -- never silently falls back to
   the other provider, which would charge a customer through a
   provider they never chose.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from api.config import settings
from api.models.billing import PaymentProvider
from api.models.organization import Organization
from api.services.billing_providers.base import BillingProvider, ProviderNotConfiguredError


def get_provider(provider: PaymentProvider | str) -> BillingProvider:
    """Direct lookup by provider name -- used by both webhook endpoints
    (which already know their own provider from the URL path) and by
    resolve_provider_for_organization below."""
    from api.services.billing_paystack import PaystackProvider
    from api.services.billing_stripe import StripeProvider

    key = provider.value if isinstance(provider, PaymentProvider) else provider
    if key == PaymentProvider.stripe.value:
        return StripeProvider()
    if key == PaymentProvider.paystack.value:
        return PaystackProvider()
    raise ValueError(f"Unknown billing provider {key!r}")


def _paystack_countries() -> set[str]:
    return {c.strip().upper() for c in settings.PAYSTACK_COUNTRIES.split(",") if c.strip()}


async def resolve_provider_for_organization(db: AsyncSession, organization_id: uuid.UUID) -> BillingProvider:
    """Real resolution, not a stub -- reads the organization's own
    `billing_country`. Raises ProviderNotConfiguredError (not a generic
    Exception) if the resolved provider has no real secret key set, so
    every caller (the router) can present one honest 501, exactly like
    this codebase's pre-existing Stripe-only endpoints already did."""
    org = await db.get(Organization, organization_id)
    country = (org.billing_country or "").upper() if org else ""

    if country in _paystack_countries():
        provider = get_provider(PaymentProvider.paystack)
    else:
        provider = get_provider(settings.DEFAULT_BILLING_PROVIDER)

    if not provider.is_configured():
        raise ProviderNotConfiguredError(
            f"Resolved billing provider {provider.name!r} for this organization is not configured on this deployment "
            f"-- set its secret key in .env to enable real payments."
        )
    return provider

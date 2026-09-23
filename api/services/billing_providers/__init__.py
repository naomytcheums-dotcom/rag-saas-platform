"""Phase 5, Étape 2 -- billing provider abstraction (Stripe + Paystack).

`BillingProvider` is the shared interface both real implementations
(`stripe_provider.StripeProvider`, `paystack_provider.PaystackProvider`)
satisfy; `registry.resolve_provider_for_organization` is the one place
that decides WHICH provider a given organization's checkout/portal/
webhook calls actually go through. Nothing else in this codebase should
import `billing_stripe`/`billing_paystack` directly for a real payment
action -- go through the registry so a deployment that adds
`PAYSTACK_SECRET_KEY` to `.env` gets Paystack working for African
organizations with zero code changes, exactly as this étape's own spec
requires.
"""

from api.services.billing_providers.base import BillingProvider, ProviderNotConfiguredError
from api.services.billing_providers.registry import get_provider, resolve_provider_for_organization

__all__ = ["BillingProvider", "ProviderNotConfiguredError", "get_provider", "resolve_provider_for_organization"]

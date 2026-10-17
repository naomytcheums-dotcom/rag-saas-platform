"""BILL-013: a Paystack organization buying a credit pack got a 500 (AttributeError: PaystackProvider had no create_credit_pack_checkout).
Paystack pack payments are now implemented (one-off transaction + signed charge.success webhook, see tests/contracts/test_paystack_credits.py). What
stays true, and is checked here: a Paystack organization NEVER gets a crash, and without a configured Paystack key the answer is the clean 501 that
names the missing configuration, with nothing created."""

import pytest

from api.config import settings
from api.services.billing_paystack import PaystackNotConfiguredError, PaystackProvider
from api.services.billing_providers.base import BillingProvider, ProviderNotConfiguredError
from test_billing_credit_packs import _auth_header, _register_and_create_org


def test_the_paystack_provider_is_a_billing_provider():
    assert issubclass(PaystackProvider, BillingProvider)
    assert issubclass(PaystackNotConfiguredError, ProviderNotConfiguredError)


async def test_paystack_credit_pack_checkout_without_a_key_is_a_clean_not_configured_error(monkeypatch):
    monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", None)
    # The key is checked before any database access or network call: nothing is created for an unconfigured provider.
    with pytest.raises(PaystackNotConfiguredError, match="Paystack is not configured"):
        await PaystackProvider().create_credit_pack_checkout(_NoDatabase(), "00000000-0000-0000-0000-000000000000", pack={"id": "pro", "price_cents": 1}, email="a@b.c", org_name="x")


class _NoDatabase:
    """Any use of the database before the key check would be a defect: fail loudly."""

    def __getattr__(self, name):
        raise AssertionError(f"the database was touched ({name}) before the Paystack key was checked")


async def test_the_credit_checkout_route_answers_501_for_an_unconfigured_paystack_organization(monkeypatch, client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)
    monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", None)

    async def _paystack(db, organization_id):
        return PaystackProvider()

    monkeypatch.setattr("api.routers.billing.resolve_provider_for_organization", _paystack)
    response = await client.post(f"/organizations/{org_id}/billing/credits/checkout", json={"pack_id": "pro"}, headers=_auth_header(token))

    assert response.status_code == 501 and "Paystack is not configured" in response.json()["detail"]

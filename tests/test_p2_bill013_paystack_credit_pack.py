"""BILL-013: a Paystack organization buying a credit pack got a 500 (AttributeError: PaystackProvider had no create_credit_pack_checkout).
Paystack pack payments are not implemented (no verifiable provider flow without a real key), so the honest answer is the 501 every
provider without pack support gives (BillingProvider.create_credit_pack_checkout), never a crash."""

import pytest

from api.services.billing_paystack import PaystackProvider
from api.services.billing_providers.base import BillingProvider
from test_billing_credit_packs import _auth_header, _register_and_create_org


def test_the_paystack_provider_is_a_billing_provider():
    assert issubclass(PaystackProvider, BillingProvider)


async def test_paystack_credit_pack_checkout_is_a_clean_not_implemented():
    with pytest.raises(NotImplementedError, match="does not support credit pack purchases"):
        await PaystackProvider().create_credit_pack_checkout(None, None, pack={}, email="a@b.c", org_name="x")


async def test_the_credit_checkout_route_answers_501_for_a_paystack_organization(monkeypatch, client, register_payload):
    token, org_id = await _register_and_create_org(client, register_payload)

    async def _paystack(db, organization_id):
        return PaystackProvider()

    monkeypatch.setattr("api.routers.billing.resolve_provider_for_organization", _paystack)
    response = await client.post(f"/organizations/{org_id}/billing/credits/checkout", json={"pack_id": "pro"}, headers=_auth_header(token))

    assert response.status_code == 501 and "does not support credit pack purchases" in response.json()["detail"]

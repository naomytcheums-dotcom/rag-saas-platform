"""BILL-018: a credit pack is charged in CREDIT_PACK_CURRENCY, so the pack list must say so (the interface used to format every pack price
in EUR while Stripe charged USD)."""

from api.config import settings
from api.security.credit_packs import CREDIT_PACKS
from test_billing_credit_packs import _auth_header, _register_and_create_org


async def test_every_pack_states_the_currency_it_is_charged_in(client, register_payload, monkeypatch):
    token, org_id = await _register_and_create_org(client, register_payload)

    monkeypatch.setattr(settings, "CREDIT_PACK_CURRENCY", "usd")
    response = await client.get(f"/organizations/{org_id}/billing/credits/packs", headers=_auth_header(token))

    assert response.status_code == 200
    packs = response.json()
    assert [p["id"] for p in packs] == [p["id"] for p in CREDIT_PACKS]
    assert {p["currency"] for p in packs} == {"USD"}
    assert [p["price_cents"] for p in packs] == [p["price_cents"] for p in CREDIT_PACKS]  # the amounts themselves are untouched


async def test_the_currency_follows_the_setting(client, register_payload, monkeypatch):
    token, org_id = await _register_and_create_org(client, register_payload)
    monkeypatch.setattr(settings, "CREDIT_PACK_CURRENCY", "eur")

    packs = (await client.get(f"/organizations/{org_id}/billing/credits/packs", headers=_auth_header(token))).json()

    assert {p["currency"] for p in packs} == {"EUR"}


def test_the_catalog_itself_carries_no_currency_so_it_cannot_disagree_with_the_setting():
    assert all("currency" not in pack for pack in CREDIT_PACKS)

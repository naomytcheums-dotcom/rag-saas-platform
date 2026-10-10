"""BILL-014: credit-pack grants are idempotent per Stripe CHECKOUT SESSION (not only per event id), deferred payments are honoured, and the
currency is checked. Stripe is not called: the webhook handler gets synthetic events, as in tests/test_billing_credit_packs.py."""

import uuid

from api.security.credit_packs import get_credit_pack
from api.services import billing_stripe
from test_billing_credit_packs import _balance, _org_with_credit, _paid_session_event

STARTER = get_credit_pack("starter")["credits"]


async def _deliver(db_session, event) -> bool:
    applied = await billing_stripe.handle_stripe_webhook(db_session, event)
    await db_session.commit()
    return applied


async def test_two_different_events_for_the_same_checkout_session_grant_once(db_session):
    org_id = await _org_with_credit(db_session, balance=0)

    await _deliver(db_session, _paid_session_event(org_id, "starter", session_id="cs_dup"))
    await _deliver(db_session, _paid_session_event(org_id, "starter", session_id="cs_dup"))  # another event id, same session

    assert await _balance(db_session, org_id) == STARTER


async def test_two_different_sessions_both_grant(db_session):
    org_id = await _org_with_credit(db_session, balance=0)

    await _deliver(db_session, _paid_session_event(org_id, "starter", session_id="cs_one"))
    await _deliver(db_session, _paid_session_event(org_id, "starter", session_id="cs_two"))

    assert await _balance(db_session, org_id) == 2 * STARTER


async def test_a_deferred_payment_grants_when_it_succeeds_and_only_once(db_session):
    org_id = await _org_with_credit(db_session, balance=0)

    await _deliver(db_session, _paid_session_event(org_id, "starter", payment_status="unpaid", session_id="cs_sepa"))
    assert await _balance(db_session, org_id) == 0  # a SEPA / bank-transfer checkout is not paid yet

    succeeded = _paid_session_event(org_id, "starter", session_id="cs_sepa")
    succeeded["type"] = "checkout.session.async_payment_succeeded"
    await _deliver(db_session, succeeded)
    assert await _balance(db_session, org_id) == STARTER

    again = _paid_session_event(org_id, "starter", session_id="cs_sepa")
    again["type"] = "checkout.session.async_payment_succeeded"
    await _deliver(db_session, again)
    assert await _balance(db_session, org_id) == STARTER  # a second delivery under another event id grants nothing more


async def test_a_session_completed_after_a_deferred_success_does_not_grant_twice(db_session):
    org_id = await _org_with_credit(db_session, balance=0)
    succeeded = _paid_session_event(org_id, "starter", session_id="cs_order")
    succeeded["type"] = "checkout.session.async_payment_succeeded"

    await _deliver(db_session, succeeded)
    await _deliver(db_session, _paid_session_event(org_id, "starter", session_id="cs_order"))

    assert await _balance(db_session, org_id) == STARTER


async def test_a_failed_deferred_payment_grants_nothing(db_session):
    org_id = await _org_with_credit(db_session, balance=0)
    failed = _paid_session_event(org_id, "starter", payment_status="unpaid", session_id="cs_failed")
    failed["type"] = "checkout.session.async_payment_failed"

    await _deliver(db_session, failed)

    assert await _balance(db_session, org_id) == 0


async def test_a_paid_session_in_another_currency_grants_nothing(db_session):
    org_id = await _org_with_credit(db_session, balance=0)
    event = _paid_session_event(org_id, "starter", session_id=f"cs_{uuid.uuid4().hex}")
    event["data"]["object"]["currency"] = "jpy"  # the pack is priced in CREDIT_PACK_CURRENCY; the same number in another currency is not its price

    await _deliver(db_session, event)

    assert await _balance(db_session, org_id) == 0


async def test_a_paid_session_in_the_packs_currency_grants(db_session):
    from api.config import settings

    org_id = await _org_with_credit(db_session, balance=0)
    event = _paid_session_event(org_id, "starter", session_id=f"cs_{uuid.uuid4().hex}")
    event["data"]["object"]["currency"] = settings.CREDIT_PACK_CURRENCY.upper()

    await _deliver(db_session, event)

    assert await _balance(db_session, org_id) == STARTER


async def test_a_session_without_an_id_grants_nothing(db_session):
    org_id = await _org_with_credit(db_session, balance=0)
    event = _paid_session_event(org_id, "starter")
    event["data"]["object"]["id"] = None

    await _deliver(db_session, event)

    assert await _balance(db_session, org_id) == 0

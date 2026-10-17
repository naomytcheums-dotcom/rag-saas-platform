#!/usr/bin/env python
"""Real validation of 12.1.10 (credit packs bought through Paystack) with the product's own Paystack adapter, against Paystack's API in TEST mode.

    RUN_LIVE_VENDOR_VALIDATION=1 PAYSTACK_SECRET_KEY=sk_test_... python scripts/validate_paystack_live.py

Refuses a LIVE key (sk_live_...): this script must never create a real charge. It initializes (does not pay) one transaction for the smallest credit pack and checks
that Paystack accepted the amount/currency/reference/metadata the product sends and returned a hosted payment URL; then that the product's webhook signature check
accepts a payload signed with the same key and rejects a tampered one. Paying the transaction with a Paystack test card and receiving the real webhook (needs a public
URL, e.g. a tunnel) remains a manual step: open the printed URL, pay with a test card, and watch POST /billing/paystack/webhook grant the credits.
"""
import asyncio
import hashlib
import hmac
import json
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(__file__))
import _live_vendor as live  # noqa: E402


async def main() -> int:
    live.require_opt_in("Paystack (test mode)", "nothing: a Paystack test transaction is initialized, not paid")
    report = live.Report("paystack_credits")
    key = os.environ.get("PAYSTACK_SECRET_KEY", "")
    if not key:
        report.skipped("paystack", "PAYSTACK_SECRET_KEY is not in the process environment")
        return report.finish()
    if not key.startswith("sk_test_"):
        report.skipped("paystack", "refusing a key that is not a Paystack TEST key (sk_test_...)")
        return report.finish()
    paystack = live.product("api.services.billing_paystack")
    config = live.product("api.config")
    config.settings.PAYSTACK_SECRET_KEY = key
    from api.security.credit_packs import get_credit_pack

    pack = get_credit_pack("starter")

    async def initialize():
        async with paystack._client() as client:
            response = await client.post("/transaction/initialize", json={
                "email": "validation@example.com", "amount": pack["price_cents"], "currency": config.settings.CREDIT_PACK_CURRENCY.upper(),
                "reference": f"credits-validation-{uuid.uuid4().hex[:12]}",
                "metadata": {"organization_id": str(uuid.uuid4()), "kind": "credit_pack", "pack_id": pack["id"]},
            })
        body = paystack._raise_for_paystack_error(response)
        url = body["data"]["authorization_url"]
        assert url.startswith("https://checkout.paystack.com/"), url
        return {"authorization_url": url, "next": "pay it with a Paystack test card to see the webhook"}

    await report.check("initialize", initialize)

    async def signature():
        payload = json.dumps({"event": "charge.success", "data": {"id": 1}}).encode()
        good = hmac.new(key.encode(), payload, hashlib.sha512).hexdigest()
        assert paystack.verify_webhook_signature(payload, good)["event"] == "charge.success"
        try:
            paystack.verify_webhook_signature(payload + b" ", good)
        except ValueError:
            return {"tampered_payload": "rejected"}
        raise AssertionError("a tampered payload was accepted")

    await report.check("webhook-signature", signature)
    return report.finish()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

"""E2E finding 2026-10-12: outbound webhooks were signed over the body only, so a recorded delivery could be replayed. V2 signs "<timestamp>.<body>"."""

import hashlib
import hmac
import json

from api.services.webhooks import sign_webhook_payload, sign_webhook_payload_v2

PAYLOAD = {"event": "document.processed", "id": 7}


def test_v2_signs_the_timestamp_and_the_canonical_body():
    body = json.dumps(PAYLOAD, sort_keys=True)
    expected = hmac.new(b"s3cret", f"1700000000.{body}".encode(), hashlib.sha256).hexdigest()
    assert sign_webhook_payload_v2(PAYLOAD, "s3cret", 1700000000) == expected


def test_a_replayed_body_with_a_new_timestamp_does_not_verify():
    old = sign_webhook_payload_v2(PAYLOAD, "s3cret", 1700000000)
    assert sign_webhook_payload_v2(PAYLOAD, "s3cret", 1700000999) != old


def test_the_original_signature_is_unchanged_for_existing_receivers():
    body = json.dumps(PAYLOAD, sort_keys=True).encode()
    assert sign_webhook_payload(PAYLOAD, "s3cret") == hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()

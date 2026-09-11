"""Partie 15.1 -- the pure transform functions
(normalize_email/normalize_phone/normalize_date) and apply_mapping's
own real, honest edge cases (unmapped connections, unknown transform
names, a missing source field)."""

import uuid

from api.models.integrations import IntegrationMapping
from api.services.integrations import apply_mapping, normalize_date, normalize_email, normalize_phone


def test_normalize_email_strips_and_lowercases():
    assert normalize_email("  Test@Example.COM  ") == "test@example.com"


def test_normalize_phone_keeps_only_digits_and_leading_plus():
    assert normalize_phone("+1 (555) 123-4567") == "+15551234567"


def test_normalize_date_handles_multiple_real_formats():
    assert normalize_date("2026-01-15") == "2026-01-15"
    assert normalize_date("15/01/2026") == "2026-01-15"
    assert normalize_date("01/15/2026") == "2026-01-15"


def test_normalize_date_returns_unchanged_on_unrecognized_format():
    # Never crashes on a real, malformed external payload -- returned
    # as-is rather than raising.
    assert normalize_date("not-a-date") == "not-a-date"


def test_apply_mapping_with_no_mappings_returns_payload_unchanged():
    payload = {"Email": "Test@Example.com"}
    assert apply_mapping(payload, []) == payload


def test_apply_mapping_applies_the_named_transform():
    mapping = IntegrationMapping(connection_id=uuid.uuid4(), source_field="Email", target_field="email", transform="normalize_email")
    result = apply_mapping({"Email": "  Test@Example.COM  "}, [mapping])
    assert result == {"email": "test@example.com"}


def test_apply_mapping_skips_a_missing_source_field():
    mapping = IntegrationMapping(connection_id=uuid.uuid4(), source_field="Phone", target_field="phone", transform="normalize_phone")
    result = apply_mapping({"Email": "test@example.com"}, [mapping])
    assert result == {}


def test_apply_mapping_unknown_transform_is_a_no_op_not_a_crash():
    mapping = IntegrationMapping(connection_id=uuid.uuid4(), source_field="Note", target_field="note", transform="not_a_real_transform")
    result = apply_mapping({"Note": "hello"}, [mapping])
    assert result == {"note": "hello"}

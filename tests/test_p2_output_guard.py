"""Specs 10.2.3 / 10.2.5 / 10.2.6 / 10.2.8 / 10.2.10 -- output guard and unsafe tool-call detection."""

import pytest

from api.services.output_guard import detect_unsafe_tool_call, redact_output, scan_output, validate_output

FAKE_AWS = "AKIA" + "ABCDEFGHIJKLMNOP"
FAKE_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijklmnop"


def test_credentials_are_always_redacted():
    text = f"key {FAKE_AWS} and token {FAKE_JWT} and postgresql://user:secret@db.example.com:5432/app"
    cleaned, findings = redact_output(text, mask_pii=False)
    assert FAKE_AWS not in cleaned and FAKE_JWT not in cleaned and "secret@" not in cleaned
    assert {f["type"] for f in findings} >= {"aws_access_key", "jwt", "database_url"}
    assert "[REDACTED:aws_access_key]" in cleaned


def test_private_key_blocks_and_api_keys_are_detected():
    types = {f["type"] for f in scan_output("-----BEGIN RSA PRIVATE KEY-----\nabc\nand sk-ant-api03-abcdefghijklmnopqrstuvwx")}
    assert {"private_key", "api_key"} <= types


def test_pii_is_masked_only_when_asked():
    text = "Write to jane.doe@example.com or call +33 6 12 34 56 78. IBAN FR76 3000 6000 0112 3456 7890 189."
    masked, findings = redact_output(text, mask_pii=True)
    assert "jane.doe@example.com" not in masked and "[EMAIL]" in masked and "[PHONE]" in masked and "[IBAN]" in masked
    assert {f["type"] for f in findings} >= {"email", "phone", "iban"}
    kept, kept_findings = redact_output(text, mask_pii=False)
    assert kept == text and kept_findings == []


def test_only_valid_card_numbers_are_masked():
    masked, findings = redact_output("card 4111 1111 1111 1111 order number 1234 5678 9012 3456", mask_pii=True)
    assert "[CARD]" in masked and "4111" not in masked
    assert "1234 5678 9012 3456" in masked  # fails the Luhn check: an order number, not a card
    assert [f for f in findings if f["type"] == "card_number"][0]["count"] == 1


def test_ordinary_text_is_untouched_and_findings_never_contain_the_data():
    text = "The meeting is on 12 March at 3pm, room 42. Contact the front desk."
    assert redact_output(text) == (text, [])
    _cleaned, findings = redact_output("mail me: jane.doe@example.com")
    assert "jane" not in str(findings)


def test_output_validation():
    assert validate_output("fine") == []
    assert validate_output("   ") == ["empty"] and validate_output(None) == ["empty"]
    assert validate_output("x" * 11, max_chars=10) == ["too_long"]
    assert validate_output("bad\x00text") == ["control_characters"]


@pytest.mark.parametrize("url", ["http://localhost:8000/admin", "http://127.0.0.1/", "http://169.254.169.254/latest/meta-data", "https://10.0.0.5/x",
                                 "http://metadata.google.internal/", "http://[::1]/", "http://db.internal/"])
def test_internal_urls_are_blocked_in_tool_arguments(url):
    assert "internal_url" in detect_unsafe_tool_call("url_reader", {"url": url})


def test_public_urls_and_ordinary_arguments_pass():
    assert detect_unsafe_tool_call("url_reader", {"url": "https://example.com/page"}) == []
    assert detect_unsafe_tool_call("calculator", {"expression": "2+2"}) == []
    assert detect_unsafe_tool_call("web_search", {"query": "how to drop a table in my garden"}) == []


def test_credentials_in_arguments_are_flagged_as_exfiltration():
    assert detect_unsafe_tool_call("http_request", {"url": "https://example.com/?k=" + FAKE_AWS}) == ["credential_in_arguments"]


def test_destructive_sql_is_flagged_only_for_sql_tools():
    assert detect_unsafe_tool_call("sql_query", {"query": "DROP TABLE users"}) == ["destructive_sql"]
    assert detect_unsafe_tool_call("sql_query", {"query": "SELECT * FROM documents LIMIT 5"}) == []
    assert detect_unsafe_tool_call("search_kb", {"query": "drop table"}) == []


def test_org_settings_default_to_off_for_the_output_guard():
    from api.security.organization_settings import DEFAULT_SETTINGS

    assert DEFAULT_SETTINGS["output_guard_enabled"] is False and DEFAULT_SETTINGS["output_guard_mask_pii"] is True

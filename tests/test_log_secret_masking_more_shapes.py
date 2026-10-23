"""mask_sensitive: shapes that were still leaking after the 2026-10-12 audit (SEC-009), found by probing the function with realistic lines.

Leaked before: `refresh_token=...` / `client_secret=...` (the word boundary does not fire after an underscore), `Set-Cookie` / `Cookie` values,
and `sk_live_...` / `sk_test_...` / `whsec_...` provider keys (Stripe, Paystack). Offline, fake values only; complements
tests/test_log_secret_masking.py without changing it."""

import pytest

import api.security.logging_correlation as lc

LEAKING = {
    "refresh_token pair": ("cookie refresh_token=RTVAL0123456789abc; Path=/", "RTVAL0123456789abc"),
    "client_secret pair": ("oauth exchange failed client_secret=CSVAL0123456789abcd", "CSVAL0123456789abcd"),
    "access_token pair": ("sent access_token=ATVAL0123456789abc to the provider", "ATVAL0123456789abc"),
    "prefixed api key": ("header x_api_key=XKEYVAL0123456789 rejected", "XKEYVAL0123456789"),
    "prefixed secret in a query string": ("GET /cb?session_secret=SSVAL0123456789&x=1", "SSVAL0123456789"),
    "Set-Cookie session": ("Set-Cookie: session=SESSVAL0123456789; HttpOnly; Path=/", "SESSVAL0123456789"),
    "Cookie header with two cookies": ("Cookie: csrf=CSRFVAL0123456789; sid=SIDVAL0123456789", "SIDVAL0123456789"),
    "stripe live key": ("using sk_live_STRIPEKEY0123456789abcd now", "STRIPEKEY0123456789abcd"),
    "stripe test key": ("using sk_test_STRIPEKEY0123456789abcd now", "STRIPEKEY0123456789abcd"),
    "restricted key": ("using rk_live_RESTRICTED0123456789ab now", "RESTRICTED0123456789ab"),
    "webhook signing secret": ("signature check with whsec_WEBHOOKSECRET0123456789 failed", "WEBHOOKSECRET0123456789"),
}


@pytest.mark.parametrize("name", LEAKING)
def test_the_secret_is_removed_and_the_line_stays_readable(name):
    message, secret = LEAKING[name]
    masked = lc.mask_sensitive(message)
    assert secret not in masked
    assert "***" in masked
    assert masked.split()[0] == message.split()[0]


def test_a_cookie_keeps_its_names_and_attributes_so_the_line_remains_useful():
    masked = lc.mask_sensitive("Set-Cookie: session=SESSVAL0123456789; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=3600")
    for kept in ("Set-Cookie", "session=", "HttpOnly", "Secure", "SameSite=Lax", "Path=/", "Max-Age=3600"):
        assert kept in masked


def test_every_cookie_value_of_a_cookie_header_is_masked_not_only_the_first():
    masked = lc.mask_sensitive("Cookie: a=AAAAAAAA1111; b=BBBBBBBB2222; c=CCCCCCCC3333")
    assert not any(value in masked for value in ("AAAAAAAA1111", "BBBBBBBB2222", "CCCCCCCC3333"))


@pytest.mark.parametrize("message", [
    "max_tokens=100 and 5 tokens used",
    "token_count=5 reached",
    "refresh interval is 300 seconds",
    "the client secretary signed in",
    "session started for organization 12",
    "Set-Cookie headers were counted: 3",
    "price_id=price_123 and plan sk_ not a key",
    "sk_live is the prefix Stripe documents",
    "the user logged in from 10.0.0.1",
])
def test_ordinary_lines_are_left_alone(message):
    assert lc.mask_sensitive(message) == message


@pytest.mark.parametrize("text", [
    "a-" * 20000 + "token",
    "a." * 20000 + "x",
    "a_" * 5000 + "x",
    "Cookie: " + "; ".join(f"n{i}=v{i}" for i in range(3000)),
    "Set-Cookie: " + ";" * 20000,
    "token=" + "x" * 100000,
    "a" * 100000,
], ids=["dash-chain-then-keyword", "dot-chain", "underscore-chain", "many-cookies", "empty-cookie-segments", "long-token-value", "long-alnum-run"])
def test_a_long_adversarial_line_is_masked_in_linear_time(text):
    """mask_sensitive runs on every log line: no pattern may take quadratic time on a long line (the URL-credentials pattern did on a run of letters, digits, dots and dashes such as a long base64url token: 4.5 s for 40 000 characters)."""
    import time

    started = time.perf_counter()
    lc.mask_sensitive(text)
    assert time.perf_counter() - started < 1.0


def test_a_prefixed_name_with_up_to_three_segments_is_still_masked():
    assert "VAL0123456789" not in lc.mask_sensitive("x_amz_security_token=VAL0123456789")

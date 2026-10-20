"""Skip reasons that are legitimately EXTERNAL: no local, throw-away stack can replace the missing thing.

Used by the strict-skip mode (RAG_STRICT_SKIPS=1, enabled by scripts/run_isolated_tests.py): in that mode every skipped test whose reason
is NOT matched here is turned into a failure, so a missing PostgreSQL, Redis, S3, worker or binary can no longer hide behind a skip.
A test matched here is still reported as SKIPPED (never as passed) and is listed as BLOCKED_EXTERNAL in the reports."""

import re

# (category, pattern on the skip reason, what is missing)
EXTERNAL_SKIPS = (
    ("payment-provider-sandbox", r"needs a real (STRIPE_SECRET_KEY|PAYSTACK_SECRET_KEY)", "a Stripe / Paystack sandbox account and key"),
    ("third-party-account", r"(GOOGLE_DRIVE|ONEDRIVE)_REFRESH_TOKEN/CLIENT_ID/CLIENT_SECRET are not configured", "a Google Drive / OneDrive OAuth grant"),
    ("third-party-account", r"NOTION_API_TOKEN is not configured", "a Notion integration token"),
    ("hosted-staging", r"Live staging tests require RAG_STAGING_TESTS=YES", "the hosted staging database and its guarded runner"),
    ("hosted-staging", r"Staging-only tenant policies are not provisioned", "the hosted staging catalog (77+ policies provisioned outside the migrations)"),
)
_COMPILED = tuple((category, re.compile(pattern), missing) for category, pattern, missing in EXTERNAL_SKIPS)


def external_category(reason: str) -> str | None:
    for category, pattern, _missing in _COMPILED:
        if pattern.search(reason or ""):
            return category
    return None

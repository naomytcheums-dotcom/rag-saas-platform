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
    # Opt-in or heavy by design (tests/llm_optin, tests/contracts): they need a paid key or a local model server, or tooling that is not installed
    # (Windows SAPI + node + Playwright, the nginx image, a Jaeger). Still reported as SKIPPED; the owner decides when to provide them.
    ("opt-in-real-llm", r"real-LLM tests are opt-in", "RUN_REAL_LLM_TESTS=1 and a local Ollama or a provider key"),
    ("heavy-local-tooling", r"needs Windows SAPI \(pywin32\), node, Playwright", "SAPI voices, node, Playwright and the frontend node_modules"),
    ("heavy-local-tooling", r"docker with the nginx:[\d.]+-alpine image is needed", "Docker with the nginx image pulled (a download this machine makes very slowly)"),
    ("heavy-local-tooling", r"the local Jaeger \(OTLP 4318 / query 16686\) is not running", "a local Jaeger all-in-one container"),
    ("heavy-local-tooling", r"CLAMAV_REAL_TEST_HOST is not set", "a ClamAV daemon container (clamav/clamav, a large image and signature download)"),
    ("heavy-local-tooling", r"set RUN_DEPLOY_TOOLING=1 \(needs Docker and the network\)", "Terraform / Helm / kubeconform and the provider plugins (network downloads)"),
    ("heavy-local-tooling", r"set RUN_DEPLOY_E2E=1 \(needs Docker and a built image\)", "the dedicated-tenant stacks built from Dockerfile.api (GBs of RAM and downloads)"),
    ("heavy-local-tooling", r"OTEL_REAL_TEST_JAEGER is not set", "a Jaeger all-in-one container to export spans to"),
)
_COMPILED = tuple((category, re.compile(pattern), missing) for category, pattern, missing in EXTERNAL_SKIPS)


def external_category(reason: str) -> str | None:
    for category, pattern, _missing in _COMPILED:
        if pattern.search(reason or ""):
            return category
    return None

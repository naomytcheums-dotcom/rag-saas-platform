# Sensitive settings: modes and safe defaults

Settings that change money, data exposure or host access. Defaults are the **safe** value unless stated. Verified by
`tests/test_sensitive_settings.py` (defaults, `/metrics`), `tests/test_p0_billing_no_free_paid_plan.py`, `tests/test_billing.py`,
`tests/test_p0_mcp_stdio_disabled.py`. The values actually set on a deployment are **not** visible from the repository: check them in the
host's dashboard (name, defined or not, never the secret value).

| Setting | Default | Development | Test | Production | Effect and risk |
|---|---|---|---|---|---|
| `CREDITS_ALLOW_UNPAID_TOPUP` | `False` | may be `True` on a self-hosted instance with no payment provider | `False` | **`False`** | `True` lets an organization add credits without paying (`POST …/billing/credits/purchase`) and is refused anyway when a payment provider is configured |
| `BILLING_ALLOW_SELF_SERVICE_PAID_PLANS` | `False` | `True` only without a provider | `False` | **`False`** | `True` lets an organization select a paid plan or mark its own invoice paid (audited with `self_service: true`) |
| `COOKIE_SECURE` | `True` | `False` over plain `http://localhost` | `False` in CI (the test client speaks plain HTTP) | **`True`** | `False` sends the refresh/CSRF cookies without the `Secure` flag |
| `METRICS_AUTH_TOKEN` | unset (**`/metrics` public**) | unset | unset | **set** on anything reachable from the Internet | with a token, `/metrics` requires `Authorization: Bearer <token>` |
| `METRICS_REQUIRE_AUTH` | `False` | `False` | `False` | **`True`** (recommended) | with `True` and no token, `/metrics` answers **503** instead of being public (fail closed) |
| `MCP_STDIO_ENABLED` | `False` | `False` | `False` | **`False`** | `True` allows a **superadmin** to register an MCP server that runs an OS command on the API host |
| `CLAMAV_ENABLED` | `False` | `False` | `False` | `True` if a ClamAV daemon is provisioned | antivirus scan of uploads before storage; no quarantine is kept (a refused upload is not stored) |
| `RAG_RUN_MODE` | unset | `preview` for a local interface preview | unset | **unset** | `preview` refuses to start unless every data store is local and no external credential is set (`api/security/runtime_guard.py`, `scripts/run_local_preview.py`) |

Production rule of thumb: nothing in this table should be *relaxed* in production without a written decision. The two settings that are open by
default on purpose (`METRICS_AUTH_TOKEN`, `CLAMAV_ENABLED`) are pinned by a test so that changing them is visible in review.

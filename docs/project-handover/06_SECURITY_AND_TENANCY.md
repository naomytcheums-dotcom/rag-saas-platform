# 06 - Security, identity and multi-tenancy

Tags: **[V]** read in code 2026-10-12; **[R]** executed/measured in project sessions; **[D]** documented in the repo only; **[U]** unknown. No secret value appears in this dossier. Any key that was ever pasted into a chat must be rotated (see 11).

## 1. Threat model in one paragraph
Several customers share one database and one API. The worst failures are (1) **customer A reading customer B's documents, conversations, credentials or invoices**, (2) account takeover, (3) a customer making the platform call internal addresses (SSRF) or run arbitrary code, (4) prompt injection making an agent leak data or misuse tools, (5) uncontrolled spend. The controls below address these in layers: application-level tenant filters, role checks, authentication hardening, outbound-request controls, input/output guard-rails, encryption of stored secrets and an audit trail.

## 2. Authentication [V]
| Mechanism | Where | Notes |
|---|---|---|
| Registration, e-mail verification | `api/routers/auth.py`, `verify.py`, Resend | verification token table; breached-password check, strength and similarity checks (`security/password_*.py`), password history |
| Login | `POST /auth/login` | timing side-channel mitigation (constant-time path for unknown users); persistent account lock-out; new-login notification |
| Access token | `security/jwt.py` | short-lived JWT (15 minutes per the client comment), **revocable** (`revoked_access_tokens`, cleaned daily), **signing-key rotation** (`jwt_signing_keys`, `key_rotation_history`, daily check; `JWT_PREVIOUS_SECRET_KEYS` for rollover) |
| Refresh | `POST /auth/refresh` | httpOnly cookie; **CSRF** double-submit token required on refresh/logout (`security/csrf.py`); the frontend refreshes automatically once on a 401 (`frontend/lib/api.ts`) |
| Access token storage on the client | `localStorage["access_token"]` | XSS-exposed by design; mitigated by CSP headers and Markdown sanitisation (`rehype-sanitize`) |
| 2FA | TOTP (`security/totp.py`), recovery codes, lock-out recovery by e-mail token | a 2FA bypass through linked OAuth sign-in was found and fixed on 2026-09-01 |
| WebAuthn / passkeys | `security/webauthn.py`, `webauthn_credentials` | |
| OAuth sign-in | `/auth/oauth/{provider}/*` | linking to an unverified existing account marks e-mail verified (bug fixed); consent tracking |
| Enterprise SSO | OIDC (`security/enterprise_oidc.py`, `/auth/sso/*`), domain ownership must be proven by DNS TXT (migration 0134) | **SAML not built** (D1/D9) |
| SCIM 2.0 provisioning | `/scim/v2/*`, tokens in `scim_tokens` (0141) | |
| API keys | `organization_api_keys` (scopes, expiry, rotation, quotas); agent API keys; widget auth | `require_public_api_scope("mcp:tools")` etc. |
| Sessions | `sessions` table and routes | list/revoke |
| Account deletion | two-stage with reminders, restore token, purge task | GDPR |

## 3. Authorization [V]
* Organization roles `owner/admin/manager/member/viewer` + custom roles (52-permission catalogue, Casbin). Routes use `require_permission("resource:action")` or role guards (`api/dependencies.py`, `api/security/permissions.py`, `rbac.py`).
* Guard tests: `tests/test_route_auth_classification.py` fails on any unclassified open route; `tests/test_p2_viewer_route_matrix.py` runs the viewer role across all routes. Earlier audits found five "Owner-only" routers that were really open to Admin and a permission inconsistency for the Manager role on webhooks; the code now has explicit comments about the Manager/Member default key `webhooks:read` (api/routers/webhooks.py lines ~37-72). **Re-verify role semantics before relying on them** [U beyond the tests].
* Per-resource grants only for workspaces (D11). Agent tool permissions are separate.

## 4. Multi-tenancy
### 4.1 How isolation is enforced today [V]
1. **Application filters:** every data-access function takes `organization_id` and filters on it (for example the retrieval layer filters `DocumentChunk.organization_id == organization_id` and excludes soft-deleted documents). 83 of 182 tables carry `organization_id`; child tables (messages, citations, evaluation questions/results...) inherit through a parent foreign key.
2. **Route-level membership checks:** the dependency resolving `{org_id}` verifies that the caller belongs to the organization with enough role.
3. **Cache and job scoping:** cache keys, Celery jobs and traces include the organization; the BM25 cache key includes the organization and corpus revision.
4. **Tests:** tenant-isolation tests per area, an IDOR matrix, a "cross-tenant sweep with real ids" (commit of 2026-10-05) and SQL-tool tenant-bypass tests; several were run against PostgreSQL in CI since D8 [R].
### 4.2 What is NOT in place: database-enforced isolation [V/D]
* RLS: `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` is applied to every table (migration 0002 for the first set, 0131 for the remaining 11), but **no `CREATE POLICY` exists in any migration** (searched: none) and `FORCE ROW LEVEL SECURITY` is not used.
* The application connects with a PostgreSQL role that has **BYPASSRLS** (read-only observation on 2026-10-06: role `postgres`, BYPASSRLS, zero policies) [D: README "Operator checkpoint"]. Consequence: RLS currently provides **no barrier against the application's own bugs**; its only effect is to block direct access through Supabase's public PostgREST/anon interface if that is exposed. A bug in one query's `organization_id` filter would leak across tenants and the database would not stop it.
* The decision (D2/D8): do not switch on policies blindly; staged plan = dedicated non-bypass role -> `app.current_org` per transaction -> pilot on 3 low-traffic tables -> CI against that role -> extend. Not started.
### 4.3 Specific cross-tenant risks found earlier and their status
| Finding | Status (evidence) |
|---|---|
| IDOR in MCP `get_failure_report` / `run_eval_benchmark` (any job/dataset id) | **Fixed**: organization ownership is checked [V `builtin_tools.py`] |
| SQL tool tenant-filter bypass found by red team | **Fixed** with a regex-anchored single-table SELECT subset, forbidden keywords, function-call rejection (e.g. `pg_sleep`) [V] |
| Stripe payment-method detach IDOR | **Fixed**: verified against the organization's customer [D] (mock-tested only) |
| A2A inter-tenant flaw | Fixed in Hardening Mission §15 [D] |
| OPA `user_context` never passed from HTTP callers | **Fixed for the chat stream** (`chat_stream.py` builds `{user_id, organization_id, role}` and passes it) [V]; other callers of `search_with_context` pass none, so the policy filter does not apply there (it is also off unless `OPA_ENABLED` and the organization enables it) |
| Connectors used one platform token for all tenants | **Fixed for importers and the 36 CRM routes** (per-organization encrypted credentials, default-deny 403; `CONNECTORS_ALLOW_PLATFORM_CREDENTIALS=False`, D17) [V/R]; **still open for agent tools** Gmail/Calendar/Outlook/SMTP/GitHub |
| Discord/Teams gateway webhooks unauthenticated | **Fixed** (shared secret `X-Gateway-Secret`, Teams audience check) [D] |
| Partner registration, n8n/Airbyte status without login | **Fixed** [D] |

## 5. Outbound requests and code execution
* **SSRF:** `ssrf_safe_client(...)` (resolves and pins the IP, rejects private/loopback/link-local) is used in 20 modules; 69 modules still import `httpx` directly - they were reviewed on 2026-10-11 and classified in `tests/test_outbound_http_inventory.py` (vendor-fixed hosts vs customer-controlled hosts). **Residual risk:** customer-supplied connector hosts are validated (https, public address, vendor suffix) at save and use time but called with a plain client, so a DNS rebinding between the checks is not blocked (D17).
* **Workflow `code` block:** restricted expression subset, no imports, size and result limits, repeat/format-string/method-growth protections (fixed 2026-10-11).
* **Plugins:** sandboxed in a separate image (`Dockerfile.plugin-sandbox`); JS run through a `node` subprocess.
* **MCP stdio transport:** disabled unless explicitly enabled and restricted to superadmin.

## 6. Input/output guard-rails (LLM safety)
### 6.1 Prompt-injection detector [V/R]
* Classifier: `protectai/deberta-v3-base-prompt-injection-v2` (Hugging Face, ~700 MB, CPU) at threshold 0.75 (`detect_prompt_injection`).
* **Second opinion** (`confirm_injection_with_llm`, `detect_prompt_injection_confirmed`): only messages the classifier flags are re-read by an LLM that may **clear** (answer SAFE) but never block alone; an ambiguous, hijacked or failed answer keeps the classifier's verdict. Provider/model/timeout via `PROMPT_INJECTION_CONFIRM_PROVIDER/MODEL/TIMEOUT_SECONDS` (default timeout 15 s, `PROMPT_INJECTION_LLM_CONFIRM=True`).
* **Where it runs:** (a) agent guardrails `validate_guardrails` on the input and on the retrieved context, using the two-stage function, when the agent has the detector enabled - and the **agent factory enables it by default** for agents it builds; (b) the agent-less `generate_response` path (voice), classifier only, only when the organization flag `prompt_injection_detection_enabled` (default **False**) is on. A bare agent has it off by default.
* **Measured** on `tests/data/injection_eval_set.json` (43 attacks, 49 legitimate requests, English and French, written by the maintainers): classifier alone recall 0.953, false positives 0.122; with `qwen2.5:3b` as second opinion 0.930 / 0.082; with `qwen2.5:7b` **0.930 / 0.020** (6 of the 7 initial false positives cleared). **Limits:** the second-opinion prompt was adjusted while looking at this same set (optimistic); the set is small and not real traffic; an adaptive attacker is out of scope; the 7B model ran on CPU and needs minutes to load (timeout must be raised); in hosted production a provider must be configured or the classifier verdict stands alone (12 % false positives). Measurement script: `scripts/measure_injection_two_stage.py`. Decision record: `docs/DECISIONS.md` D15.
### 6.2 Other guards
Toxicity filter (opt-in), output guard (credential redaction always when enabled; PII masking optional), blocked topics, domain allow-list, content filter level, max tokens per response, "citation required" and "context only" refusal modes, per-agent guardrail config validation, human approval.

## 7. Cryptography and secrets [V]
* Stored secrets (connector credentials, MCP credentials, API tokens, webhook secrets) are encrypted: new code uses **AES-256-GCM** (`api/security/encryption.py`: `encrypt_data` -> `key_id:nonce:ciphertext`, 12-byte random nonce, key from `ENCRYPTION_MASTER_KEY`, previous key for rotation, `encryption_key_records`, `encryption_audit`); older code uses **Fernet** (`secret_encryption.py`, AES-128-CBC + HMAC). D12 says "Fernet / AES-256-GCM" collectively - both exist. Document text and chat messages are **not** encrypted by the application (database/disk encryption is the provider's feature and was **not verified**).
* Connector credential storage requires `ENCRYPTION_MASTER_KEY`; if it is missing the PUT returns 503 (by design). **A key generated and pasted into a chat must be considered compromised; generate a new one and store it in the hosting dashboard and a password manager.** Losing the key makes stored credentials unreadable.
* Audit log integrity: each `audit_logs` row has a SHA-256 HMAC `checksum` chained to the previous row (`security/audit_log.py`, key `AUDIT_LOG_HMAC_SECRET_KEY`); a verification routine recomputes the chain; archive/purge by retention.
* Password hashing bcrypt; secrets never logged (log redaction in agent traces and handlers).
* Settings validators refuse start-up on dangerous configuration (weak JWT/session secrets under 32 characters, unimplemented `*_USE_LLM` flags enabled, cookie settings).

## 8. Rate limiting, abuse and cost
Redis-backed limiters (`security/rate_limit.py`, `adaptive_rate_limit.py`) are used by **44 of 107 router files** (auth endpoints, search `SEARCH_RATE_LIMIT_MAX_ATTEMPTS=120/60s`, public API, widget, license validation, partner registration). It is *not* applied globally; a hardening pass (§4) protected the highest-risk surfaces and fixed a fail-open case. Cost control: credit balance check before each LLM call, daily/monthly credit caps (`daily_credit_limit`, `monthly_credit_limit`), per-tool token budgets, per-organization quotas. The cap check is not proven atomic under heavy concurrency (BILL-012; PostgreSQL concurrency tests for credits/invoices/subscriptions: 24 passed [R]).

## 9. Webhooks and replay
Inbound payment webhooks verify signatures (`stripe-signature`; Paystack signature) and record events in `payment_events` for idempotence (race on idempotence fixed in Hardening Mission §5 [D]). Chat gateways use shared secrets. Outbound webhook deliveries (`api/services/webhooks.py`, `api/tasks/webhooks.py`) are signed with HMAC-SHA256 over the body in `X-Webhook-Signature`, with Celery retries; the signature does **not** cover a timestamp, so a receiver cannot reject replayed deliveries [V]. Slack signatures use a 5-minute replay window [V].

## 10. Privacy, GDPR and retention [V/D]
Consent records and re-consent flow; data requests (export/erasure, `data_requests`, daily processing task); data-breach register; configurable conversation retention (`conversation_retention_days`); deleted-account purge with Mem0 organization purge (`purge_organization_memory` called from the organization delete route and the account-purge task); per-document GraphRAG deletion (`delete_document_from_graph` on permanent delete). Completeness of erasure across every derived store (embeddings of deleted documents in caches, flight recordings, lineage events, logs, backups) was not independently verified. Backups: `scripts/backup.sh` covers only the **self-hosted** Docker database; for Supabase use `pg_dump` (procedure in `docs/RELEASE_RUNBOOK_2026-10-11.md`); a verified production dump (27 MB, 217 tables with data) was taken on 2026-10-11 and kept outside git; **restore has never been tested** [R].

## 11. Security tooling [R]
Bandit (non-blocking; 5 Hugging Face `from_pretrained` without pinned revision alerts remain), mypy (non-blocking, many errors), Snyk, a security-headers middleware (HSTS, CSP, X-Frame-Options, Referrer-Policy), `pip`/`npm` audits (zero advisories at the 2026-10-06 check), WeasyPrint advisories mitigated by escaping and deny-all resource fetching. A recorded red-team sweep (SSO, SQL, IDOR, dangerous primitives) is in `ROADMAP.md` [Bob-Auto-Fixes] 2026-09/10.

## 12. Residual risk summary (highest first)
1. No database-level tenant barrier; one query bug leaks across tenants (mitigated by tests, not prevented).
2. Agent tools using one server identity (Gmail/Calendar/Outlook/SMTP/GitHub).
3. Access token in localStorage.
4. Injection detector accuracy limits and dependence on a configured second-opinion provider.
5. Restore of backups never rehearsed; encryption-at-rest of the hosted database unverified.
6. 69 direct `httpx` call sites outside the SSRF-safe client (vendor-fixed hosts, but a regression risk).

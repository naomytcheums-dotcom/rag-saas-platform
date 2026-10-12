# 09 - Billing, credits, connectors and external services

Tags: **[V]** read in code 2026-10-12; **[R]** run in project sessions; **[D]** documented only; **[U]** unknown. Three levels are kept apart for every payment feature: **interface/data model exists**, **sandbox-tested with the provider's test mode**, **real money collected in production**. For this project the third level has **never been reached for any provider**.

## 1. Commercial model implemented in code [V]
### 1.1 Plans (`plans`, seeded by `api/services/admin_subscriptions.py`)
| Key | Monthly (USD cents) | Yearly | Documents | Agents | Members | Included credits / month | Notes |
|---|---:|---:|---:|---:|---:|---:|---|
| `free` | 0 | - | 50 | 3 | 5 | 1,000 | seeded on demand (`ensure_free_plan_seeded`) |
| `starter` | 4,900 | 49,000 | 100 | 3 | 5 | 10,000 | |
| `pro` | 19,900 | 199,000 | 1,000 | 10 | 20 | (see code) | priority support, advanced features |
| `enterprise` | 99,900 | 999,000 | unlimited | unlimited | unlimited | (see code) | |
Plan limits are derived from the organization's real subscription state (BILL-007, 2026-10-09), so an unpaid organization cannot keep paid limits. Admins can edit plans (`Admin Subscriptions`, 16 routes). Trial support: `Subscription.trial_ends_at` (migration 0094).
### 1.2 Prepaid credits (D13) [V: `api/security/credit_packs.py`, `api/services/billing_credits.py`]
* Conversion: 1 credit = 1 API request = 100 input tokens = 50 output tokens = 1 processed document; 10 credits = 1 MB storage.
* Packs (fixed in code): Starter 10,000 credits for 9.99 USD; Pro 100,000 for 79.99; Business 500,000 for 349.99; Enterprise 1,000,000 for 599.99 (`CREDIT_PACK_CURRENCY=usd`).
* Ledger: `credits` (balance) + `credit_transactions` (types `purchase`, `consume`, `refund`, `grant`). The monthly plan allotment is granted by the beat task `grant-monthly-plan-credits`; `auto-refill-credits-daily` tops up when configured.
* Consumption: the agent runtime checks the balance before each LLM call and debits after the call with the provider-reported usage; if credits run out mid-run the run stops with an explicit error. **BYOK**: an organization that stores its own provider key (`organization_llm_configs`) is not debited. Spend caps: `daily_credit_limit`, `monthly_credit_limit` in organization settings (checked in `enforce_spend_caps`, before the call); atomicity under heavy concurrency is not proven (BILL-012). Balance rows are locked with `SELECT ... FOR UPDATE`; the PostgreSQL concurrency tests (24) passed on a scratch database [R].
* **Free-credit tap (fixed in Hardening Mission §23, ROADMAP "robinet de crédits gratuits"):** `POST .../billing/credits/purchase` used to grant credits without payment. Now `CREDITS_ALLOW_UNPAID_TOPUP=False` (default): credits come only from a confirmed checkout (webhook). Enabling it is only for self-hosted/development deployments with no payment provider. **Check it is `false` on Render.**
* Similarly `BILLING_ALLOW_SELF_SERVICE_PAID_PLANS=False` (default): `subscribe/upgrade/downgrade` to a paid plan and `invoices/{id}/pay` by hand are refused (402/403) unless a confirmed checkout happened (BILL-001/002).
### 1.3 Invoices, usage, alerts [V]
Monthly invoice generation, overdue marking, reminders (beat tasks), invoice PDF (WeasyPrint, escaped content, deny-all resource fetching), send/void/pay routes (`pay` restricted by the flag above), usage breakdown and forecast, usage alerts, display currency/country endpoints (`billing/country`, `billing/display-currency`).
### 1.4 Coupons (D5) [V]
`POST /organizations/{id}/billing/coupons/redeem` records a redemption (`coupons`, `coupon_redemptions`, migration 0140). A `percent_off` coupon is **recorded but not applied at checkout** (it needs provider-side coupon objects and a sandbox with the owner's test keys).
### 1.5 Partners, resellers, licences, sales models [V/D]
`resellers`, `sub_clients`, `partner_commissions` (monthly calculation, daily payout task), referral codes, `licenses` (daily validation task, rate-limited `LICENSE_VALIDATE_*`), four sales models (SaaS, self-hosted, partner, white-label) in `Sales` routes. Payouts to partners are database records; **no real payout rail is integrated** [U].

## 2. Payment providers: what exists and what is usable
| Provider | Code | Test mode run? | Usable for this owner? |
|---|---|---|---|
| **Stripe** | `billing_stripe.py` (checkout session, customer portal, subscriptions, invoices, payment methods, webhook with `stripe-signature` verification via `STRIPE_WEBHOOK_SECRET`, cancel at provider since BILL-006) | Mocked tests only; **no call to Stripe's API was ever made** [D] | **No**: Stripe requires a business in a supported country (D16) |
| **Paystack** | `billing_paystack.py` (+ migration 0115 multi-provider) | Mocked tests only [D] | **No**: Paystack does not serve Cameroon (D16); the registry routes only `NG,GH,ZA,KE` billing countries to it |
| **CinetPay** | **not implemented** | n/a | Chosen target (mobile money MTN/Orange + cards) pending: can an individual without a company open an account, which documents, are USD/EUR enabled, foreign cards accepted, test keys, settlement. The connector must follow CinetPay's current official documentation and be run in its test mode first (D16). Flutterwave / Notch Pay are fallbacks |
| Flutterwave | not integrated (D14) | n/a | |
Provider selection (`billing_providers/registry.py`): billing country in `PAYSTACK_COUNTRIES` -> Paystack, else `DEFAULT_BILLING_PROVIDER` (default Stripe); **if the resolved provider has no secret key configured, an error is raised - no silent fallback** to the other provider. With no keys set (the current default), every checkout fails closed and the product has no way to collect money.
`BillingProvider` (`billing_providers/base.py`) is the interface a CinetPay adapter must implement: customer, checkout session, portal, cancel, invoices, payment methods, webhook parsing.
### Refunds and disputes (BILL-016) [D]
`payment_events` stores provider events for idempotence, but **refund events (`charge.refunded`) are not handled** and invoices have no link to the provider charge; credits are not taken back on refund. An admin refund route is mentioned in `billing_stripe.py` comments. A fix needs a schema change and a policy decision (are credits reclaimed, what about consumed credits).
### Failed payments / dunning [U]
Overdue marking and reminder e-mails exist as beat tasks; the full behaviour on a failed renewal at the provider (grace period, suspension) was not traced end to end. Admin suspension fields exist (`0089`).

## 3. External services inventory
`Mode` = how credentials are held: **S** server-wide environment variable; **O** per organization (encrypted); **B** bring-your-own-key per organization.
| Service | Purpose | Mode | Local stand-in used in tests | Status |
|---|---|---|---|---|
| Supabase PostgreSQL + pgvector | primary database | S | Docker `pgvector/pgvector` | production DB migrated to 0143 [R] |
| Redis | cache, rate limit, Celery broker | S | Docker redis | [R] local; production instance [U] |
| S3-compatible storage (Supabase Storage/R2/MinIO) | files, avatars, voice, backups | S | MinIO | [R] local |
| LLM: Anthropic, OpenAI, Mistral, Gemini, watsonx, OpenAI-compatible | generation | S, B | **Ollama** `qwen2.5:3b` / `7b` (11 real tests pass) | local real; hosted providers only via opt-in tests that were not run routinely |
| Embeddings: sentence-transformers (local); OpenAI, Voyage, Cohere (service only) | vectors | S | local models | [R] |
| Resend | e-mail (verification, reset, notifications) | S | placeholder key | **not exercised against the real service** in the audit |
| Tavily | web search tool | S | none | not exercised |
| ClamAV | antivirus | S | Docker clamav | real-daemon test passed [R]; disabled by default |
| Tesseract/poppler, Whisper-style STT, Deepgram, Google TTS, ElevenLabs, Twilio | OCR, voice | S | OCR real locally | voice providers not exercised |
| OPA | policy engine | S | none | off by default |
| Prometheus, Grafana, Loki, Tempo/Jaeger, OTLP collector, Sentry, Langfuse, Datadog LLM Obs | observability | S | Jaeger real-collector test passed [R] | hosted ones unverified |
| Slack, Microsoft Teams, Discord | chat bots | O (per organization integration rows) | none | mocked tests; real sandboxes blocked |
| Stripe, Paystack | payments | S | none | see section 2 |
| Mem0, LightRAG | memory, graph retrieval | S | none | optional |
| GitHub (importer + agent tool) | code and issues | importer: O; agent tool: S (open item) | none | importer tested with fakes |
| Gmail, Google Calendar, Outlook, SMTP (agent tools) | e-mail/calendar actions | **S - one identity for everyone (D17 open)** | none | must stay unset |
| Airbyte, n8n, Zapier, Make | integration platforms | O / webhook | n8n in observability compose | partial |
| Hugging Face Hub | model downloads | S | cache | unpinned revisions (Bandit) |
| GitHub Actions, CircleCI, Vercel, Render, Snyk | CI/CD, hosting, scanning | n/a | n/a | see 10 |

## 4. Connectors (data importers and CRM extractors)
### 4.1 Two different things (do not conflate)
1. **Data connectors for RAG** ("import my Drive/Notion/Confluence/GitHub into the knowledge base"): `api/services/*_extraction.py` + `api/tasks/*_import.py` + routes in `documents` + `external_sources` sync.
2. **Action tools for agents** (Gmail, Calendar, Outlook, SMTP, GitHub, SQL, human escalation, custom HTTP tools, MCP tools): `api/tools/*`.
### 4.2 Per-organization credential model (D17, migration 0143) [V/R]
* `PROVIDERS` in `api/services/connector_credentials.py` defines, per provider, typed fields: kinds `secret`, `text`, `url` (https, public address, optional vendor suffix such as `.salesforce.com`), `subdomain` (single label, vendor suffix appended), `dc` (Mailchimp data centre), `ident`. 40 providers: activecampaign, airtable, asana, azure_devops, basecamp, bitbucket, box, clickup, coda, confluence, docusign, dropbox, github, gitlab, google_drive (also serves google_docs), hive, hubspot, intercom, jira, klaviyo, linear, mailchimp, miro, monday, nifty, notion, onedrive, pipedrive, pipefy, podio, process_street, salesforce, shopify, smartsheet, smartsuite, teamwork, trello, woocommerce, wrike, zendesk, zoho.
* Storage: `connector_credentials(organization_id, provider, encrypted_payload)` encrypted with AES-GCM under `ENCRYPTION_MASTER_KEY`. API: `PUT/GET/DELETE /organizations/{org}/connectors/{provider}`. UI: `/dashboard/settings/connectors`.
* Runtime: a ContextVar scope (`connector_scope(provider)` as a FastAPI dependency on the 36 CRM routes and 7 importer routes; `run_in_scope` in the Celery import tasks; `connector_scope_for` in external-source sync) makes the extraction modules read credentials through a `connector_settings` proxy: inside a scope they see **only that organization's** credentials; **default-deny (403)** if the organization has none; `CONNECTORS_ALLOW_PLATFORM_CREDENTIALS=True` restores the old shared-token mode (single-tenant installs only); GitHub works without credentials for public data.
* Tests: `tests/test_connector_credentials.py` (38) + frontend tests; two settings that connectors read but did not exist (`SMARTSUITE_ACCOUNT_ID`, `BITBUCKET_API_TOKEN`) were added.
* **Residual:** DNS rebinding window for customer-supplied hosts; Google Drive/OneDrive ask the customer to paste an OAuth client and refresh token (no click-through consent flow, no operator-registered OAuth apps); agent tools still use server identities.
### 4.3 Real-service verification status
Importers/CRM extractors are tested with fake HTTP transports; **none was run against the real vendor API with real credentials**, because that requires a customer-style account at each vendor. `docs/SANDBOX_SETUP.md` was planned to list free developer sandboxes (not written).

## 5. Environment variables that matter for commercial operation (names only)
`ENCRYPTION_MASTER_KEY` (new, secret, in a vault), `CONNECTORS_ALLOW_PLATFORM_CREDENTIALS=false`, `*_ENABLED` flags of offered connectors with **no server token**, `COOKIE_SECURE=true`, `CREDITS_ALLOW_UNPAID_TOPUP=false`, `BILLING_ALLOW_SELF_SERVICE_PAID_PLANS=false`, `METRICS_AUTH_TOKEN`, `STRIPE_*`/`PAYSTACK_*` (leave empty until a provider is usable), `RESEND_API_KEY`, `DATABASE_URL`, `REDIS_URL`, `S3_*`, `JWT_SECRET_KEY` (>= 32 chars) and `JWT_PREVIOUS_SECRET_KEYS`, `SESSION_MIDDLEWARE_SECRET`, `AUDIT_LOG_HMAC_SECRET_KEY`, LLM keys or `OLLAMA_BASE_URL`, `PROMPT_INJECTION_LLM_CONFIRM` + `PROMPT_INJECTION_CONFIRM_PROVIDER/MODEL/TIMEOUT_SECONDS`, `DISCORD_GATEWAY_SHARED_SECRET`, `TEAMS_BOT_ID`. Never copy their values into documents or chats.

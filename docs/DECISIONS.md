# Decisions taken (2026-10-10)

Decisions the audit left open, with the safest choice for each. Each one can be reversed; the reason and the way back are written down.

## D1 - SAML (spec 10.4.2): keep OIDC, add SAML only on a signed customer request
- **Decision:** the platform offers OpenID Connect single sign-on (`api/routers/enterprise_sso.py`) and SCIM 2.0 provisioning. SAML 2.0 is not built.
- **Why:** SAML needs the system library `xmlsec1` and an XML-signature dependency in the production image; XML signature handling is a classic source of vulnerabilities, and the 512 MB host cannot take another native dependency. Every major identity provider (Okta, Entra ID, Google Workspace, Auth0, Keycloak) supports OIDC.
- **Way back:** when a paying customer requires SAML, add `python3-saml` behind a feature flag in a separate image, with its own security review. The `enterprise_sso_connections` model already stores a provider type.

## D2 - Tenant isolation (spec 1.3.5, audit R-01): application isolation now, database barrier staged
- **Decision:** the isolation control stays at the application layer for now and is made verifiable: route x role contract test (`tests/test_p2_viewer_route_matrix.py`), tenant-isolation tests per area, and the P0 fixes. Row Level Security is **not** switched on in production by this change.
- **Why:** turning on `FORCE ROW LEVEL SECURITY` with policies changes the behaviour of every query. A mistake locks every customer out or, worse, silently returns nothing. It cannot be validated without a PostgreSQL role that does not bypass RLS, and the current application connects with a role that does.
- **Staged plan (to be done on a staging database, never first on production):**
  1. create a dedicated application role without `BYPASSRLS`;
  2. set `app.current_org` per transaction from the authenticated membership (one dependency in `api/database.py`);
  3. pilot `FORCE RLS` plus a policy on three tables with the lowest traffic (for example `escalations`, `coupon_redemptions`, `scim_tokens`);
  4. run the whole suite against that database (the PostgreSQL tests exist, opt-in via `P0_PG_TEST_URL`) and make that job mandatory in CI;
  5. extend table by table.
- **Way back:** each step is a separate migration with a downgrade.

## D3 - Product name and logo (spec 14.4.1, 14.4.2): the name is chosen, the logo is not
- **Decision (2026-10-11, owner):** the product name is "RAG SaaS Platform", which is what the interface already shows. No logo is invented (14.4.2 stays open). `docs/commercial/BRAND_GUIDE.md` lists what to check when publishing (e-mail sender, widget title, PDFs); all customer-facing text is in `locales/`.
- **Advice, not a blocker:** a descriptive name is hard to protect and to rank on; check it in the trademark databases of the target markets, the `.com` / `.ai` domains and the app-store / npm / PyPI namespaces before investing in marketing.

## D4 - End-to-end browser tests (spec 13.2.4, 13.3.7): Playwright in a separate package
- **Decision:** `e2e/` is its own npm package (Playwright 1.49.1, uses the Chrome already installed, no browser download). It starts the isolated API (SQLite, every external service blanked, refuses non-local URLs) and the frontend, and never touches production.
- **Why separate:** no change to the dependencies of the shipped frontend; the tests are opt-in (`cd e2e && npm install && npx playwright test`).

## D5 - Promo codes of type percent-off
- **Decision:** recorded at redemption, not applied automatically at checkout.
- **Why:** applying a discount to Stripe / Paystack needs provider-side coupon objects and has to be validated in each provider's sandbox with the owner's test keys.

## D6 - Code formatter (spec 13.1.3): ruff format instead of Black
- **Decision:** `ruff format` is the project formatter. Its output is designed to match Black's, so the spec's goal (one uniform, automatic style) is met without a second tool.
- **Why:** adding Black next to ruff would mean two formatters that can disagree, and a large reformatting diff for no gain. Revisit only if the team wants Black's exact behaviour on edge cases.

## D7 - Interface languages: French and English only (until further notice)
- **Decision:** `UI_SUPPORTED_LANGUAGES` is `["fr", "en"]`; the Spanish, German, Portuguese and Arabic bundles were removed. An unsupported `Accept-Language` falls back to the default language.
- **Why:** the owner asked to ship two languages first. To add a language back: create `locales/<code>/common.json`, add the code to `UI_SUPPORTED_LANGUAGES`, `scripts/sync_frontend_locales.py`, `frontend/lib/i18n.tsx` and `frontend/components/LanguageMenu.tsx`.

## D8 - Tenant isolation: application filters are the barrier, PostgreSQL integration tests run in CI (spec 1.3.5, 13.2.10)
- **Decision:** isolation between organizations stays enforced by the application (every query is scoped by `organization_id`, every route by a `require_*` dependency; `tests/test_route_auth_classification.py` fails on any new open route). A database-level barrier (row-level security with `FORCE` and policies keyed on a per-request setting) is **not** switched on automatically: doing it blindly can lock the application out of its own tables, so it needs a staged rollout on a copy of production first.
- **What changed:** the CI job `backend-tests` now starts a disposable pgvector PostgreSQL, applies every migration and runs the PostgreSQL integration files (`tests/test_postgres_integration.py`, `tests/test_rbac_integration.py`, ...) against it. Locally: 61 passed, 1 skipped (a staging-only policy check).
- **Still to decide (owner):** when to roll out RLS policies (see `scripts/staging_validate.py` for the staging procedure).

## D9 - SAML single sign-on (spec 10.4.2): not built without a security review
- **Decision:** not implemented in this change. `agents.md` forbids changing security code without review, and a hand-written SAML flow is a classic source of authentication bypasses. OIDC SSO (`/auth/sso/*`) and SCIM provisioning (`/scim/v2/*`) already exist.
- **When needed:** use the maintained open-source library `python3-saml` (needs the native `xmlsec1` library in `Dockerfile.api`), behind a feature flag, with a review of the assertion validation, replay protection and account linking, and a test against a real identity provider (for example Keycloak, free) in staging.

## D10 - What "enterprise roles" means (spec 10.4.4)
- **Definition adopted:** the built-in organization roles (owner, admin, manager, member, viewer) plus the organization's **custom roles** (`/organizations/{id}/rbac/*`, Casbin policies), assigned manually or provisioned through SCIM. No separate role family is added.

## D11 - Per-resource permission grants (spec 1.2.8)
- **Scope today:** a grant is accepted and enforced only for the resource types that really check it (workspaces). Other pairs are rejected with HTTP 400 instead of being stored as grants that nothing reads (`api/security/resource_permissions.py`). Agent tool permissions have their own enforcement (`api/services/agent_permissions.py`).
- **Extending it** to documents, conversations or knowledge bases means adding the check to each router and a test per type; it is security code, so it goes through review.

## D12 - Encryption at rest (spec 10.1.14)
- **In the application:** secrets (API keys, tokens, webhook secrets) are encrypted with Fernet / AES-256-GCM before they are stored. Document text and chat messages are **not** encrypted by the application.
- **At the provider:** disk-level encryption of the database and of object storage is the provider's feature. It is documented by Supabase for its managed databases and storage, but it was **not verified from this repository**: the owner should confirm it in the Supabase project settings and note the result here.

## D13 - Usage billing (spec 12.1.9): prepaid credits, not post-paid invoices
- **Decision:** usage is paid through prepaid credits that are debited as the product is used (`billing_usage`, credit ledger, spend caps). The platform does not send metered usage to Stripe or Paystack to be invoiced afterwards.
- **Why:** prepaid credits cannot create unpaid debt, which fits the "no free paid plans" rule (BILL-007). If metered invoicing is wanted later, Stripe's usage records can be added next to the ledger without replacing it.
- **Known limit:** the spend caps are not proven atomic under heavy concurrency (BILL-012); a load test on PostgreSQL is still to do.

## D14 - Payment providers (spec 12.1.1): Stripe and Paystack, no Flutterwave
- **Decision:** Flutterwave is not integrated. Stripe covers cards worldwide and Paystack covers the African markets the spec targets.
- **Still to do by the owner:** run both providers in their test mode with the owner's test keys (checkout, webhook, refund). Nothing in this repository has been run against a real provider sandbox.
- **Superseded in part by D16 (2026-10-11):** the owner cannot open a Stripe account (it needs a company in a Stripe country) and Paystack is not available in Cameroon.

## D15 - Prompt-injection detector (specs 10.1.8, 10.2.1, 10.2.2): measured, flag rather than block
- **Measured (2026-10-11):** `protectai/deberta-v3-base-prompt-injection-v2` at threshold 0.75 on `tests/data/injection_eval_set.json` (43 attacks, 49 legitimate requests, English and French): recall 0.953 (41/43), false positive rate 0.122 (6/49). Three of the six false positives are French requests (password reset, privacy policy, two-factor authentication). `tests/test_prompt_injection_measured.py` (opt-in) fails below recall 0.90 or above 0.15 false positives.
- **Correction (2026-10-11):** the detector is off by default on a bare agent (`prompt_injection_detection_enabled=false` in the database) but ON for every agent built by `api/services/agent_factory.py` (`create_rag_agent`), so the false positives do reach customers.
- **Decision:** threshold tuning cannot fix it (the wrong verdicts score 0.97 to 1.0). A message the classifier flags is now re-read by a language model (`PROMPT_INJECTION_LLM_CONFIRM`, default on) that can CLEAR it but never block on its own; no answer, an error or an unclear answer keeps the classifier's verdict. Only flagged messages cost an LLM call. Built and unit-tested with a fake model; the combined recall and false positive rate with a real model still have to be measured (`tests/test_prompt_injection_measured.py` measures the classifier alone).
- **Limit:** the set is small and written by the maintainers; it is not the rate on real traffic and says nothing about an adaptive attacker.

## D16 - Payment providers (supersedes D14 in part): CinetPay first, owner constraints
- **Owner constraints (stated 2026-10-11):** no company, so no Stripe; Paystack does not serve Cameroon; Cameroon-based freelancer who wants mobile money (MTN, Orange) and foreign cards.
- **Decision:** the next provider to implement behind `BillingProvider` is CinetPay, then Flutterwave or Notch Pay if CinetPay cannot accept foreign currencies for a Cameroon account. Credits stay prepaid (D13), which suits mobile money.
- **Not decided / to ask the provider in writing:** can an individual without a company open an account, which documents, are USD and EUR enabled for a Cameroon account, are foreign Visa/Mastercard accepted, test keys available, settlement to MTN / Orange / a Cameroon bank in XAF. CinetPay documents a separate test mode (`sk_test_` keys, `api.cinetpay.net`) in its JS SDK and the currencies XOF, XAF, GNF, CDF, USD; its older documentation says a Cameroon account can only initiate payments in XAF. PayPal is not documented by CinetPay.
- **Nothing is implemented yet:** the connector must follow CinetPay's current official API documentation and be run against its test mode with the owner's test keys.

## D17 - Importers and CRM connectors used ONE platform-wide credential (found and fixed 2026-10-11)
- **Fixed (2026-10-11):** every organization now stores its OWN credentials (`PUT /organizations/{org_id}/connectors/{provider}`, encrypted with `ENCRYPTION_MASTER_KEY`, migration 0143, screen *Settings > Connected accounts*). The 36 CRM routes, the 7 document importer routes, their background tasks and the external-source sync run inside that organization's scope: the connector modules see ONLY its values (a missing field is `None`, never the server's). An organization with nothing connected gets a 403, the server's token is never used (`CONNECTORS_ALLOW_PLATFORM_CREDENTIALS=false`, the default). Addresses typed by a customer are validated (https, public address checked at save and at use, vendor domain for vendor-hosted services, strict formats for values spliced into URLs). GitHub keeps working for public data with no credentials. 38 tests (`tests/test_connector_credentials.py`) fail without the guards; the 419 older tests of these modules pass with the legacy shared mode switched on by `tests/conftest.py`.
- **For the operator:** to offer a connector to customers set its `*_ENABLED=true` (no token needed on the server). `CONNECTORS_ALLOW_PLATFORM_CREDENTIALS=true` restores the old shared mode and is only for a single-tenant installation. `ENCRYPTION_MASTER_KEY` must be set or credentials cannot be stored (503).
- **Residual risk:** a customer-supplied host is checked (https, public address) at save time and at use time, but the HTTP call is a plain httpx call, so a DNS answer that changes in between (DNS rebinding) is not blocked. Moving those 40 calls to `ssrf_safe_client()` closes it (tests/test_outbound_http_inventory.py explains).
- **Also found on the way:** `SMARTSUITE_ACCOUNT_ID` and `BITBUCKET_API_TOKEN` were read by their connectors but missing from the settings, so those two could never run in shared mode; added.
- **Still open:** Google Drive and OneDrive ask the customer to paste an OAuth client and refresh token (bring your own app); a click-through "Connect with Google / Microsoft" consent flow needs OAuth apps registered by the operator. The agent tools `email_tools`, `calendar_tools` and `github_tools` (api/tools) still read server-wide credentials (`GMAIL_*`, `GOOGLE_CALENDAR_*`, `OUTLOOK_*`, `AGENT_SMTP_*`, `GITHUB_API_TOKEN`), all blank by default: if the operator fills them in, the agents of EVERY organization can read and send mail and calendar entries as the operator. Leave them blank in a multi-tenant deployment until they get the same per-organization treatment. Nothing was run against a real vendor account.

### Original finding (kept for the record)
- **Finding:** the 36 routes of `api/routers/crm.py` (Jira, Zendesk, HubSpot, Salesforce, Shopify...) and the document importers (Google Drive, OneDrive, Confluence, Notion, GitHub) read their token from server settings (`JIRA_API_TOKEN`, `ZENDESK_API_TOKEN`, `CONFLUENCE_BASE_URL`...). There is no per-organization credential storage. Every one of them is guarded only by `documents:write`, an ordinary member permission.
- **Consequences:** (1) a customer cannot connect THEIR OWN Jira, Zendesk or Drive: the product cannot honestly be sold as "connect your tools" yet; (2) if the operator switches a connector on (`JIRA_ENABLED=true` plus a token), every organization's members import from the OPERATOR's account. Both are blocked today only because every connector is off by default (`*_ENABLED=False`).
- **Do not enable any of these connectors in production** until one of the following is built: per-organization encrypted credentials (and OAuth for Google, Microsoft, Notion, Slack), or at minimum a superadmin-only guard on these routes.
- **Not done here:** it is a feature (storage, encryption, UI, OAuth apps registered with each vendor), not a patch, and the existing tests of these routes assume the shared-credential behaviour.

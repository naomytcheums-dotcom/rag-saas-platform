# 04 - Critical and high findings

## 1.1.10 Suppression du compte - HIGH
- status: PARTIALLY_IMPLEMENTED (code assessment before test gate: PARTIALLY_IMPLEMENTED; confidence MEDIUM)
- evidence: DELETE /account/me (api/routers/account.py:328), purge task api/tasks/account_purge.py, restore flow (account_restore.py, restore-account page); UI deleteAccount in profile page
- gap: permanent deletion depends on a Celery purge job; no worker in the production image (audit R-02), so deletion may never become permanent
- security: soft delete then purge; restore tokens
- external blockers: Celery worker in production
- action: run worker/beat and verify the purge on staging

## 1.3.5 Isolation des données - CRITICAL
- status: PARTIALLY_IMPLEMENTED (code assessment before test gate: PARTIALLY_IMPLEMENTED; confidence HIGH)
- evidence: org-scoped filters in services/routers; tests such as tests/test_p0_chat_conversation_isolation.py
- gap: one forgotten filter exposes another tenant; opt-in PostgreSQL tests are not in CI
- security: NO database-level barrier: RLS enabled without FORCE and without policies (audit R-01)
- external blockers: PostgreSQL
- action: decide the RLS strategy (audit P0-1) and add a contract test per route

## 5.4.8 Bloc Code - HIGH
- status: IMPLEMENTED_UNVERIFIED (code assessment before test gate: IMPLEMENTED_UNVERIFIED; confidence MEDIUM)
- evidence: api/services/workflow_block_code.py; sandbox api/routers/sandbox.py, models/sandbox.py
- gap: sandbox isolation (process/container) not verified
- security: code execution is the highest-risk block; isolation strength not assessed here
- external blockers: sandbox runtime
- action: security review of the sandbox

## 10.1.12 Malware scanning - HIGH
- status: BLOCKED_EXTERNAL (code assessment before test gate: BLOCKED_EXTERNAL; confidence MEDIUM)
- evidence: api/services/clamav.py wired in api/security/documents.py; CLAMAV_ENABLED defaults off
- gap: scanner not running in production (audit)
- security: when disabled, uploads are not scanned
- external blockers: ClamAV daemon
- action: run ClamAV or document the risk

## 12.1.1 Checkout - HIGH
- status: PARTIALLY_IMPLEMENTED (code assessment before test gate: PARTIALLY_IMPLEMENTED; confidence HIGH)
- evidence: checkout via Stripe and Paystack: api/services/billing_stripe.py, billing_paystack.py; UI POST /organizations/{id}/billing/checkout (billing/page.tsx:229); webhooks in billing.py:511,538
- gap: Flutterwave named in the spec is absent; never run against a real provider sandbox; live tests are skipped (audit R-05)
- security: webhook signature verification, no free paid plans (P0 fix)
- external blockers: Stripe/Paystack test keys
- action: run sandbox end to end; decide on Flutterwave

## 12.1.2 Subscriptions - HIGH
- status: IMPLEMENTED_UNVERIFIED (code assessment before test gate: IMPLEMENTED_UNVERIFIED; confidence HIGH)
- evidence: subscription lifecycle in billing_stripe.py / billing_paystack.py / admin_subscriptions; UI subscribe/cancel/reactivate
- gap: never run against a real provider sandbox; live tests are skipped (audit R-05); recurring renewal events not observed
- security: row locks added
- external blockers: Stripe/Paystack
- action: sandbox renewal scenario

## 12.1.10 Credits - HIGH
- status: IMPLEMENTED_UNVERIFIED (code assessment before test gate: IMPLEMENTED_UNVERIFIED; confidence HIGH)
- evidence: credits: api/services/billing_credits.py, credit packs, preflight in orchestrator; UI credits on billing page
- gap: Paystack credit purchase not supported; currency inconsistency (BILL-018); never run against a real provider sandbox; live tests are skipped (audit R-05)
- security: unpaid top-up flag CREDITS_ALLOW_UNPAID_TOPUP must be false in production (owner action)
- external blockers: Stripe/Paystack
- action: sandbox credit purchase; set the flag

## 12.3.1 AI credits - HIGH
- status: IMPLEMENTED_UNVERIFIED (code assessment before test gate: IMPLEMENTED_UNVERIFIED; confidence HIGH)
- evidence: AI credits (see 12.1.10)
- gap: never run against a real provider sandbox; live tests are skipped (audit R-05)
- security: no free responses without credits (P0 fix)
- external blockers: Stripe/Paystack
- action: see 12.1.10

## 13.2.10 Database tests - HIGH
- status: PARTIALLY_IMPLEMENTED (code assessment before test gate: PARTIALLY_IMPLEMENTED; confidence MEDIUM)
- evidence: PostgreSQL concurrency tests exist (test_postgres_*.py) but are opt-in and not in CI
- gap: database behaviour proven on SQLite in CI only
- security: n/a
- external blockers: PostgreSQL service
- action: audit P1-4

## 13.3.8 Deploy - HIGH
- status: PARTIALLY_IMPLEMENTED (code assessment before test gate: PARTIALLY_IMPLEMENTED; confidence MEDIUM)
- evidence: Render/Vercel redeploy from git pushes (platform-managed); no CI deploy job; migrations not applied automatically (audit R-03)
- gap: no automated migration step; deployment is not a pipeline stage
- security: n/a
- external blockers: Render/Vercel
- action: add a controlled migration step


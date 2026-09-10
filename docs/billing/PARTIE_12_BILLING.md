# Partie 12 — Billing (Plans, Stripe, Credits/Usage, Invoices, UI)

One consolidated guide, same discipline as
[`docs/security/PARTIE_10_SECURITY.md`](../security/PARTIE_10_SECURITY.md) and
[`docs/admin/PARTIE_11_ADMIN_DASHBOARD.md`](../admin/PARTIE_11_ADMIN_DASHBOARD.md) --
cross-reference this file from wherever the literal spec asked for a
dozen separate `PLANS.md`/`STRIPE.md`/`CREDITS.md`/`INVOICES.md`/`UI.md` files.

## 12.1 — Plans

`Plan`/`Subscription` already existed for real (Partie 11.4,
`api/models/admin.py`) -- extended here rather than duplicated: annual
pricing (`yearly_price_cents`), `max_api_keys`/`max_webhooks`/
`max_requests_per_month`, and `priority_support`/`advanced_features`/`sla`
flags. `GET /billing/plans` and `/billing/plans/{id}` are public (a plan
catalog is marketing content, not organization data) -- admin CRUD stays
on the real, existing `/admin/plans` (11.4), never duplicated.
Subscription lifecycle (`subscribe`/`upgrade`/`downgrade`/`cancel`/
`reactivate`) lives under `/organizations/{org_id}/billing/...`, this
codebase's real, established org-scoped convention, not the literal
spec's flat `/billing/subscription` (which has no way to know which
organization a multi-org user means).

## 12.2 — Stripe

`api/services/billing_stripe.py` -- real Stripe SDK (`stripe==11.4.1`)
calls: customer creation, checkout session, billing portal session,
payment methods, subscription cancellation, invoice listing, and a
real webhook handler with signature verification
(`stripe.Webhook.construct_event`) and idempotency (`StripeEvent`, since
Stripe guarantees at-least-once delivery). **Honest scope**: this
environment has no real Stripe account -- `STRIPE_SECRET_KEY` is unset,
so every function raises `StripeNotConfiguredError`, surfaced as a real
`501 Not Implemented`, not a simulated success. The moment a real key is
set, every function makes a real API call -- nothing here is mocked
internally.

## 12.3 — Credits / usage

`Credit`/`CreditTransaction` (new, `api/models/billing.py`) track a
spendable balance; real usage COUNTING is NOT duplicated -- it reuses
the already-real, generic `organization_usage`/`organization_usage_details`
ledger (`api/security/usage.py`, Partie 1.3.8). `check_limits`
(`api/services/billing_usage.py`) checks real monthly usage against the
real `Plan.max_*` columns. 4 fixed credit packs
(`api/security/credit_packs.py`, same "static catalog, not a DB table"
pattern as `permission_catalog.py`'s 52 permissions).

## 12.4 — Invoices

`Invoice`/`InvoiceLine` (new). Sequential numbering
(`INV-<year>-<seq>`), real VAT calculation, PDF generation via
WeasyPrint -- the exact same lazy-import pattern already established by
`api/services/conversation_export.py`'s `export_to_pdf` (Partie 8),
including the same honest `PDFUnavailableError` when WeasyPrint's native
libraries aren't installed. `api/tasks/billing.py`'s
`generate_monthly_invoices` creates one real invoice per active,
genuinely-paid subscription (`monthly_price_cents > 0`) once a month --
a free plan never gets an invoice.

🐛 **Real bug found and fixed**: `api/database.py`'s `get_db()` never
auto-commits (same class of bug as Partie 10.1's RBAC permission
catalog) -- nearly every mutating endpoint in `api/routers/billing.py`
was silently rolling back on session close. Found via live browser
testing: the credits balance displayed correctly (in-memory, pre-commit)
but no `CreditTransaction` row ever persisted, and a page reload reset
the balance. Fixed by adding an explicit `await db.commit()` to every
mutating endpoint; re-verified live (a real purchase now shows up in
transaction history after a fresh page load).

## 12.5 — Frontend

One consolidated page, `frontend/app/dashboard/billing/page.tsx`, 6
tabs (Overview/Plans/Usage/Credits/Invoices/Payment) -- same
consolidation discipline as Security (10.6) and Admin (11), not the
literal spec's ~40 separate component files. Verified live: real free
plan, real signup credit grant (1000, from `CREDITS_DEFAULT_AMOUNT`),
real credit pack purchase reflected immediately in balance and
transaction history.

## 2026-09-10 data-cleanup note

Before this part, the real dev database (Supabase Postgres, not the
isolated in-memory SQLite the test suite uses) had accumulated 108 junk
`organizations` rows, all created by this repo's own integration/e2e
test suites (`test_e2e_lifecycle.py`, `test_avatar_storage_integration.py`,
`test_branding_storage_integration.py`, ...), which deliberately run
against real infrastructure rather than mocks. 107 were orphaned by a
second real bug (see `api/tasks/account_purge.py` -- `organizations` has
no owner FK, so `ON DELETE CASCADE` never reached it when the sole
member was purged); both bugs are now fixed. Cleaned up after explicit
user confirmation -- the real database now shows 0 organizations, 1 real
user, matching the actual state of this deployment (no real customers
yet), not a fabricated or stale number.

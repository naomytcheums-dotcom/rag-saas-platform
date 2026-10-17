# 03 — Isolation multi-tenant

Remediation session of 2026-10-10 (branch `bob/auto-fix-20261010-1555`, based on `main` `6619bc5`). Statuses: VERIFIED, FIXED, PARTIAL, BLOCKED_EXTERNAL, NOT_RUN, NOT_VERIFIED, ACCEPTED_RISK.

## Decision (documented, justified)
Defence in depth, introduced **progressively**: (1) explicit application filters stay the primary control; (2) PostgreSQL RLS policies become a second barrier,
table by table; (3) the barrier only becomes effective when the application stops connecting with a role that bypasses RLS. A global blind RLS migration was
refused: with today's single bypassing role it would change nothing, and with a plain role it would break every path that runs without a tenant (login, webhooks,
Celery, superadmin) — those need a separate system role first. Nothing was applied to any remote database.

## State re-verified today (empty PostgreSQL 17 built by `alembic upgrade head`, local disposable database)
| Fact | Value | Proof |
|---|---|---|
| Application tables | 179 (177 models + `casbin_rule` + `alembic_version`) | information_schema |
| RLS enabled | 178 (all but `alembic_version`) | `pg_class.relrowsecurity` |
| FORCE RLS | 0 | `pg_class.relforcerowsecurity` |
| Policies before 0137 | 0 | `pg_policies` |
| Policies after 0137 | 6 (documents, document_chunks, credits, credit_transactions, invoices, evaluation_datasets) | round trip 0136→0137→0136→0137: 6 / 0 / 6 |
| Role used by the application in production | **NOT VERIFIED** (documented as `postgres` with BYPASSRLS in 0098; the hosted database was not inspected) | BLOCKED_EXTERNAL |
| `organization_id` columns | 80, all `uuid` | information_schema |

With RLS enabled and no policy, a plain role sees nothing (default deny); a superuser / BYPASSRLS / owner sees everything. FORCE RLS does not protect against a bypassing
role and was deliberately not set.

## What was built
- `api/db_tenant_context.py`: `bind_tenant(db, org_id)` sets the **transaction-local** `app.current_org_id` and an `after_begin` listener re-applies it to every later
  transaction of the session. It cannot leak across pooled connections (SET LOCAL semantics, also behind a transaction-mode pooler), survives commits and sends no SQL on SQLite.
  Called by `require_org_member` after the membership check (so a non-member never gets a context).
- Migration `0137_tenant_rls_policies_pilot` (additive, idempotent, reversible, existing migrations untouched): `tenant_isolation` policy with `USING` and `WITH CHECK`
  `organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid` on the 6 pilot tables. No declared organization ⇒ NULL ⇒ nothing visible or writable (fail closed).
- Tests: `tests/test_postgres_tenant_rls.py` (8, disposable PostgreSQL, throw-away schema and role): plain role sees only its organization; sees and writes nothing without context;
  cannot update, delete or insert into another tenant (the other tenant's rows are intact); context survives a commit; does not leak to the next pooled session; superuser unaffected;
  mutation proof (a permissive policy leaks both tenants; no policy = deny); statements idempotent. `tests/test_tenant_context_wiring.py` (3), `tests/test_p0_tenant_route_contract.py` (4),
  `tests/test_migration_chain_integrity.py` (4). **They fail if the isolation is removed** (mutation proof in the RLS test; synthetic unguarded router in the contract test).

## Access paths (cartography)
| Path | Tenant filter today | Tenant context for RLS | Gap |
|---|---|---|---|
| API routes with `{org_id}` (374 operations) | membership/permission guard declared on every one except 2 public-by-design routes (VERIFIED by contract test) | yes (`bind_tenant`) | guard correctness per query is covered by IDOR tests, not proven exhaustively |
| API routes addressed by another id (`/documents/{id}`, `/datasets/{id}`, `/jobs/{id}`...) | loaded then checked in services/dependencies (e.g. `require_dataset_admin`) | **no** (org unknown until loaded) | candidate IDOR class: needs per-route review (NOT_VERIFIED); `tests/test_document_idor.py`, `test_billing_idor.py`, `test_a2a_idor.py` cover samples |
| API-key authenticated requests (public API, A2A, widget) | organization taken from the key | no | to wire with the system-role design |
| Celery tasks | explicit ids | no | system role (bypass) required; tasks taking a bare id without org check not audited |
| Webhooks (Stripe, Paystack, Slack, Twilio...) | resolved from provider ids | no | system role |
| MCP / A2A | per-organization keys/servers; `tests/test_a2a_idor.py` | no | |
| Superadmin / admin routes | role guards (`require_admin`, `require_superadmin`) | not applicable: must bypass by design | exception documented and tested (route audit tests) |
| Vector search (pgvector / numpy fallback) | `organization_id` in the retrieval queries (central ones; annex paths not exhaustively audited) | no | `document_chunks` is a pilot table: the first place where the policy will bite |
| SDK, exports | through the API | as above | |

## Table matrix
`03-tenant-table-matrix.csv` — 177 tables: 80 organization-owned, 51 children of tenant tables (indirect isolation), 26 user-owned, 6 system/global, 1 the organization row itself, 13 to analyse; per table:
class, current RLS, current policy, target policy, execution role, regression risk, required tests, dependencies. Risk "élevé" for tables read before the tenant is known (organizations,
organization_members, users/sessions, API keys, audit_logs, payment_events...) or written outside a request (webhooks, Celery).

## Rollout plan (each step needs its own approval and a staging rehearsal)
1. (external) Create a non-owner, non-BYPASSRLS runtime role and a separate migration role; keep the current role for migrations and a system role (BYPASSRLS) for Celery/webhooks/superadmin.
2. Point `DATABASE_URL` of the API at the runtime role **in staging**; the 6 pilot tables enforce isolation; run the full suite on PostgreSQL (the new CI job + the opt-in tests).
3. Extend context propagation: API-key paths (org from the key), system tasks explicitly choosing the system role.
4. Add policies in batches following the matrix (documents family, evaluation family, billing family, agents family ...), each with its cross-tenant PostgreSQL test.
5. User tables (`app.current_user_id`) and pre-authentication flows last.
Rollback: `alembic downgrade -1` drops the pilot policies; switching the runtime role back restores today's behaviour.

## Residual risks
Isolation in production still rests on application filters until step 2 (ACCEPTED_RISK until then, stated in the release readiness report). The 13 "to analyse" and 51 "child" tables
have no designed policy yet.

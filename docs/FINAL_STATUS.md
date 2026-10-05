# Final status - evidence available on 2026-10-04

## Latest parallel backup evidence - 22:30 local time

Real Supabase dump now **SUCCESS**: pg_dump 17.11, 911502 bytes,
178 public table definitions, timestamped SQL file ignored by Git.
Header checked; SHA256 and exact procedure in
[BACKUP_RESTORE.md](./operations/BACKUP_RESTORE.md).
The earlier "no Supabase dump" / absent-client statuses below are historical.

Restore remains **BLOCKED_EXTERNAL**: user confirmed Supabase free-project
limit, authorized Docker fallback, but desktop-linux and default Docker
daemon checks both time out (20 seconds each). No container created and no
restore counts claimed. The full dump includes Supabase platform extensions,
so its portability must also be tested, not assumed.

Eight real staging API diagnostic probes and existing feature alternatives
completed independently: 117 cases, zero failures/skips, 1438.999s.
109 assertion-based alternative tests pass; eight probes recorded outcomes,
not successful live journeys. Storage/provider errors remain explicit:
chat HTTP 200 contains an SSE error, STT/TTS return 400, TXT/PNG uploads
raise missing-S3 OSError. Preparation/read paths work in documented scope.
See [PARALLEL_TASKS_REPORT.md](./audit/PARALLEL_TASKS_REPORT.md).

## Latest complete backend run

JUnit `mission-backend-confirmation.xml`: **5,408 tests collected,
5,354 passed, 54 skipped, 0 failed, 23 deselected**, 10,680.761 seconds.
The run used `.venv\Scripts\python.exe`, started
2026-10-04 20:51:26.534212 +01:00 and ended 2026-10-04
23:49:27.295212 +01:00. The 54 conditional integration skips and 23
deselected tests remain outside the passing evidence. Two Qdrant destructor
exceptions were logged at interpreter shutdown after pytest's summary.

### Historique des runs backend

- 2026-10-04 17:01: première suite complète, 5,262 passés,
  44 échoués, 65 ignorés, 23 désélectionnés.
- 2026-10-04 18:52: rejeu ciblé, 77 passés, 2 échoués.
- 2026-10-04 20:49: trois tests Resend/RLS ciblés passés.
- Le run de confirmation ci-dessus est le résultat courant ;
  ces résultats précédents sont conservés comme historique.

## Executive decision

- **Application: PARTIEL.**
- **Security: PARTIEL, not globally certified.**
- **Production ready: NON.**
- Every item in this requested follow-up is either verified in its stated
  scope or explicitly blocked/partial below. This is a documented audit
  checkpoint, not a claim that the entire application works at 100%.
- No production access, deployment, commit or push; historical migrations
  0001-0132 unchanged. Production revision 0130 is user-declared only.

## Test results

| Scope | Verified result |
|---|---|
| Latest complete backend run | 5408 collected: 5354 passed, 54 skipped, 0 failed; 23 deselected; 10680.761s |
| Initial complete run (historical) | 5262 passed, 44 failed, 65 skipped; 23 deselected; 2948.90s |
| Replay including new regressions (historical) | 77 passed / 79, 2 failed, 0 skipped/errors; 131.686s |
| Live staging A/B RLS and IDOR after policies | 11/11 passed, 0 skipped; 202.76s |
| Role guard / runner regressions | 29/29 passed |
| Frontend | 116/116 passed, type-check PASS, lint 0 errors/warnings |
| Ruff on URL/role changes and tests | PASS |

Runs overlap and must not be added. The latest full pytest run has zero
failures. Passing provider-contract tests do not prove actual email delivery;
mocked unit tests do not prove live provider behavior. The sitemap network
failures passed a real retry and are not attributed to code fixes.

Every original failure is individually classified in
[BACKEND_FAILURE_REGISTER.md](./audit/BACKEND_FAILURE_REGISTER.md);
corrections are recorded in [CHANGE_LEDGER.md](./audit/CHANGE_LEDGER.md).
The old 4993/125/208 run is historical, not the current baseline.

## Skips and deselections - not hidden

Original 65 skips: 7 avatar S3, 6 branding S3, 1 orphan-avatar S3,
24 document S3 pipeline, 4 Paystack sandbox, 4 Stripe sandbox,
1 live worker ping, 2 Google Drive, 2 OneDrive, 1 Notion,
1 Tesseract, 1 Tesseract/poppler, 11 guarded staging tests.
The eleven guarded staging cases were subsequently executed and all passed.
The remaining 54 skipped integration checks are **not certified**:
their storage/provider accounts, worker or binaries were unavailable.
The original 23 deselections remain outside the observed result;
no passing result is attributed to them.

## Database, isolation and security

Supabase staging `<STAGING_PROJECT_REF>`: official session pooler, revision
0132 visually verified in Table Editor, 178 public tables (including Alembic),
pgvector 0.8.2 and HNSW. Backend readiness DB/Redis/cache OK; Redis is local
and isolated, not a claimed Supabase Redis service.

Two actual browser-created users/organizations A/B log in and are API-isolated.
Nine representative IDOR surfaces pass in both directions: document, agent,
workflow, conversation, evaluation, media, MCP, A2A and billing.
Those are ASGI calls with real PostgreSQL rows and scoped test identities,
not exhaustive all-verbs/all-subroutes penetration testing.

77 tenant policies target only the NOLOGIN, non-superuser, non-BYPASS
`rag_staging_tenant` lab role on direct UUID organization_id tables.
DB tests prove missing context denies documents, A/B each see only their
own document, and cross-tenant reassignment is rejected.
Initial SET ROLE denial was corrected by explicit SET TRUE, INHERIT FALSE
membership for the already-bypassing staging administrator.

**Limits:** API/worker runtime still connects as a bypass role. The lab GUC
is trusted caller-supplied, not independently identity-bound. Indirect
tenancy, excluded audit/global tables and all runtime jobs are not covered
by this DB proof. Do not claim complete DB-enforced tenant isolation.
Follow-up specialist review found no new exploitable issue in the role
guards and synchronous URL conversion; this is not a whole-project review.

## Features

All twenty requested journeys are listed with exact evidence in
[UI_FEATURE_REPORT.md](./audit/UI_FEATURE_REPORT.md):
**6 bounded API passes, 6 partial, 8 blocked**.

Verified bounded actions: workspace, agent, workflow draft, evaluation
dataset creation; credits display API; webhook registration. Read APIs for
tools/KB, MCP, notifications, branding and analytics work within documented
scope. Registration/login/logout browser A/B previously validated.

Not demonstrated end to end: PDF/DOCX/TXT ingestion and embeddings,
chat/citation quality, runnable workflow execution, real evaluations/results,
external MCP calls, STT/TTS, image pipeline, alert delivery, branding editing
and payment/provider integrations. Source existence and mocked unit tests
do not prove these configured live services work.

## Backup, production plan and remaining blockers

- **BLOCKED_EXTERNAL_PROVIDER:** actual email delivery is not certified by
  provider-contract tests that may accept provider rejection responses.
- **BLOCKED_EXTERNAL:** storage, sandbox providers and current live worker
  missing for the documented skipped/blocked journeys.
- **BLOCKED_EXTERNAL_PROVIDER:** the staging dump exists, but restore to a
  disposable database and rollback remain unverified; Docker server probe
  timed out and the second Supabase project was unavailable.
  [BACKUP_RESTORE.md](./operations/BACKUP_RESTORE.md) records the procedure.
- **NOT VERIFIED:** original deselections, application-wide runtime RLS, comprehensive security review,
  representative load testing and all twenty browser E2E journeys.
- Production migration plan 0130 -> 0131 -> 0132 updated with risks,
  prerequisites and data-loss-aware rollback; **not applied**:
  [PRODUCTION_MIGRATION_PLAN.md](./audit/PRODUCTION_MIGRATION_PLAN.md).

No masked success or production certification is granted by this report.

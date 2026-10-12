# Phase 5 — addendum: limits closed (2026-10-12)

Scope: the owner asked that no limit stays open, no action stays partial, and that the most recommended decision be taken for every pending decision.
Labels: **EXÉCUTÉ** = run and observed, **ÉCRIT** = written but not run, **OWNER** = needs an access only the owner has.

## Decisions taken (recommended option each time)

| # | Question | Decision | Why |
|---|----------|----------|-----|
| 1 | Push the local commits to the PR branch? | Yes, pushed to `bob/auto-fix-20261010-gaps` (no force) | The branch is the PR branch, not main; CI is the only independent check. Cost: CircleCI xlarge x4, GitHub about 1 h |
| 2 | Merge PR #25? | **No** | The owner's confirmations were never given and the production revision is unverified (runbook says 0130, handover says 0143) |
| 3 | Edit migration 0133 to remove its lock contention? | No: new migration 0144 | Existing migrations are never modified (agents.md section 4.2) |
| 4 | Pilot RLS migration (`0137_tenant_rls_policies_pilot`, other branch) | Stays out of PR #25; renumber to 0145 at its merge; use a dedicated role instead of `TO PUBLIC` | `tests/test_migration_chain_contract.py` fails on a duplicated or branching revision |
| 5 | Sign Celery messages with an HMAC? | No | An attacker who can write to the broker can forge consistent messages; the effective control is broker TLS + password, now enforced in configuration |
| 6 | Delete the 19 functions with no caller? | No | A deletion is not a fix for a defect; they are listed in phase 3 |
| 7 | One extra confirmation per disposable database? | No | The name rule (test/pytest/disposable/scratch/throwaway/tmp) already refuses everything else |

## Limits closed (EXÉCUTÉ unless stated)

| Limit | Fix | Proof |
|---|---|---|
| 0133 statement triggers serialized same-organization writers (4 s measured) | `0144_bm25_revision_deferred.py`: deferrable constraint triggers, one bump per transaction at commit; downgrade restores 0133 | `tests/test_postgres_bm25_revision.py`: 4 pass on 0144, 2 fail on 0143; round trip identical; bulk 50 000 rows +0.3 to 0.5 s |
| Runbook head and Docker backup command wrong | Runbook updated (0144, `${PWD}\backups:/out`) | read back |
| Redis broker reachable over the internet without TLS/password (SEC-010) | `api/config.py` validator: public Redis must be `rediss://` with a password; private hosts exempt; `ALLOW_INSECURE_BROKER=1` overrides | `tests/test_broker_security_config.py` fails on the previous `api/config.py` (ImportError), passes now |
| Secrets in log lines whatever their shape (SEC-009) | Value-based masking of every configured secret and of database URL passwords, on top of the pattern masking | `tests/test_log_secret_masking.py`: 3 tests error on the previous code, 25 pass now |
| Secrets already stored in `system_logs` | `scripts/scrub_system_logs.py` (dry-run by default; `--apply --confirm-database <name>`; never prints content) | `tests/test_scrub_system_logs.py` pass. **OWNER**: run it against the real database (dry-run first) |
| Same defect class as TEN-011..013 could come back | `tests/test_route_parent_binding_contract.py` (route on `{org_id}` that loads an object by id alone fails the build) | 3 pass; the scan finds exactly the 5 defective routes on the unfixed code |
| Which tables can hold tenant data without an organization link (TEN-006) | `audit-reports/phase5-2026-10-12/tenant_reachability.py` classifies all 182 tables: 83 DIRECT, 1 ORG_ROOT, 23 USER_SCOPED, 63 INDIRECT, 12 GLOBAL. `tests/test_tenant_table_classification.py` pins the 12 reviewed GLOBAL tables | 2 pass. Review of the 12: catalogues/keys/platform logs/`users`/`payment_events` carry no tenant payload; `agent_memory_items` is reached only through agent routes that authorize the agent in the caller's organization; `task_plans`/`task_steps` are service-only (no route) |
| Dependabot branches built on four xlarge CircleCI containers | `.circleci/config.yml`: both jobs ignore `dependabot/*` | YAML valid; **ÉCRIT** for the effect (visible at the next dependabot push) |

## What only the owner can do (scripts ready, none executed by me)

1. `audit-reports/phase1-2026-10-12/owner_scripts/run_owner_readonly_checks.ps1`: real `alembic_version`, `rolbypassrls` of the application role, policies, row counts (read-only).
2. `download_actions_logs.ps1`: historical CI logs (needs a token with `actions:read`).
3. `scripts/scrub_system_logs.py` dry-run then `--apply` on the real database.
4. Rotate every secret that CI runs #1–#194 could read (repository secret `DATABASE_URL` and others), scope the secrets to an environment, shorten Grafana/Loki retention.
5. Decide the merge of PR #25 once the production revision is confirmed.

## Résultats exécutés après l'addendum (2026-10-12)

| Mesure | Résultat |
|---|---|
| Suite complète locale (PostgreSQL, Redis, MinIO jetables, `scripts/local_test_stack.ps1 test`) | **6 524 passés, 75 ignorés, 14 échecs** en 6 h 15. 9 échecs = `test_celery_worker_workflow` (exige Bash Linux, inapplicable sous Windows, passe sur GitHub Actions). 5 échecs = DNS transitoire (sitemaps, `/discord/send`) : **rejoués, 9 passés** |
| **Couverture mesurée de `api/`** | **85 %** (49 442 instructions, 7 239 non couvertes) : pas 90 %. `scripts/local_test_stack.ps1` la reproduit |
| GitHub Actions sur `1f26ec6` | `backend-tests`, `backend-security`, `build-backend`, `frontend-checks`, `build-frontend` : **succès** ; `mypy` et `bandit` (non bloquants) : succès/échec sans effet |
| CircleCI | `rag-pipeline-regression` succès ; `api-tests` : build 606 **échoué** (`xlarge` absent du plan), 608 **échoué** (MinIO tué, exit 137, 3 conteneurs sur 4), 610 **succès** après retour à `large` + worker Celery limité à 2 processus. Cause du 137 : probable, non prouvée |
| Vercel `erto98udjbe` | un échec transitoire sur `aa4d26f`, succès sur `1f26ec6` |

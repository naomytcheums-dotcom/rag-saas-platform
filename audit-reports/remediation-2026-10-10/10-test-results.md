# 10 — Résultats de tests (preuves observées)

Environnement : Windows, Python du venv du projet, PostgreSQL 17 + pgvector jetable (conteneur `rag-pr1-disposable-pg`, 127.0.0.1:15432), `DATABASE_URL` factice injoignable pour les tests SQLite. Aucun service réel.

| Contrôle | Résultat | Statut |
|---|---|---|
| `ruff check api` (à chaque lot) | propre | VERIFIED |
| `tests/test_runtime_guard_preview.py` | 38 passés | VERIFIED |
| Tenant / IDOR / RBAC (95 tests ciblés) | tous passés | VERIFIED |
| `tests/test_p0_tenant_route_contract.py`, `test_tenant_context_wiring.py`, `test_migration_chain_integrity.py` | passés | VERIFIED |
| `tests/test_postgres_tenant_rls.py` (8, opt-in) sur base jetable | passés | VERIFIED |
| Alembic base vide → `0137` | code 0, 5 à 16 s, une tête | VERIFIED |
| Aller-retour `0136→0137→0136→0137` | 6 / 0 / 6 politiques | VERIFIED |
| Celery config (5) + CI job (4) + sensibles (5) | passés | VERIFIED |
| Eval Lab (77 tests) dont `test_squad_eval` (17), import (4) | passés | VERIFIED |
| Facturation (41) + `bill018` (3) | passés | VERIFIED |
| `tests/docs` (323) + `test_agents_md_routes` (2) | passés | VERIFIED |
| Deployment / workspaces (28) | passés | VERIFIED |
| Vitest billing (8) ; `tsc --noEmit` | passés / propre | VERIFIED |
| Tests Celery d'intégration (8) | ignorés : base injoignable | NOT_RUN |
| Sauvegarde / restauration sur base jetable | dump 1 s, restauration 2 s, état identique | VERIFIED |
| Suite backend complète (mêmes `--ignore` que la CI, `--maxfail=50`) | 6037 passés, 3 échecs d'environnement (rejoués : 47 passés), 194 ignorés | VERIFIED (local) |
| Job GitHub `backend-postgres-tests` | jamais exécuté (aucun push) | NOT_RUN |
| CI GitHub / CircleCI sur cette branche | aucun push | NOT_RUN |
| Stripe / Paystack réels, Redis réel, worker réel, Supabase, Render | hors périmètre autorisé | BLOCKED_EXTERNAL |
| Benchmark RAG (SQuAD) | non lancé (budget / modèle à décider) | NOT_RUN |

## Suite backend complète
Lancée le 10/10/2026 à 17:42:40, terminée à 20:15:33 (2 h 30 53). Sortie : `D:\rag-work\audit-scripts\full_suite.txt`. Mêmes `--ignore` que la CI, `--maxfail=50`, `DATABASE_URL` factice injoignable, `LITELLM_LOCAL_MODEL_COST_MAP=True`.

**Résultat : 6037 passés, 3 échecs, 194 ignorés, 23 désélectionnés.**

| Échec | Cause observée | Rejeu |
|---|---|---|
| `test_admin_dashboard.py::test_system_log_handler_writes_real_rows` | `psycopg2.OperationalError` : connexion refusée sur 127.0.0.1:1. Le test écrit dans la vraie `DATABASE_URL` (voir son docstring) et mon URL factice est injoignable | passe avec `DATABASE_URL` = base jetable `rag_remediation_scratch` |
| `test_default_models_are_routable.py::test_every_proposed_hosted_model_is_known_to_the_litellm_price_map[anthropic-claude-sonnet-5-5]` | `claude-sonnet-5-5` absent de la carte de prix LiteLLM **locale** embarquée (j'avais forcé `LITELLM_LOCAL_MODEL_COST_MAP=True`) | passe sans cette variable |
| `test_default_models_are_routable.py::test_cost_pricing_matches_the_litellm_price_map[claude-sonnet-5-5-...]` | idem (`KeyError`) | passe sans cette variable |

Rejeu des 3 tests (et du fichier `test_default_models_are_routable.py`) : **47 passés**. Les 3 échecs sont donc dus à mon environnement d'exécution, non au code ni aux tests ; aucun test ni assertion modifié. Réserve : la carte de prix distante dépend du réseau et change avec le temps.

**Ignorés (194), tous NOT_RUN** : PostgreSQL d'intégration / RBAC / SSL (`DATABASE_URL` injoignable), concurrence et RLS PostgreSQL (opt-in, exécutés séparément sur la base jetable : voir plus haut), tests staging réels (`RAG_STAGING_TESTS` non défini).

## Limites
- Les tests PostgreSQL passent avec un rôle propriétaire/superuser local : ils prouvent la logique des politiques, pas leur effet avec le rôle d'exécution de production (BLOCKED_EXTERNAL).
- Les mocks de paiement ne prouvent pas le comportement des fournisseurs.
- `test_detect_user_language_falls_back_to_accept_language_header` : échec préexistant (voir rapport PR #20), non traité ici.

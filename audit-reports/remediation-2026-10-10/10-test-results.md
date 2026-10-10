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
| Suite backend complète (mêmes `--ignore` que la CI, `--maxfail=50`) | voir section ci-dessous | voir ci-dessous |
| Job GitHub `backend-postgres-tests` | jamais exécuté (aucun push) | NOT_RUN |
| CI GitHub / CircleCI sur cette branche | aucun push | NOT_RUN |
| Stripe / Paystack réels, Redis réel, worker réel, Supabase, Render | hors périmètre autorisé | BLOCKED_EXTERNAL |
| Benchmark RAG (SQuAD) | non lancé (budget / modèle à décider) | NOT_RUN |

## Suite backend complète
Lancée à 17:42 ; avancement relevé : 19 % à 18:11, 21 % à 18:13 (~2 h 30 estimées). Sortie : `D:\rag-work\audit-scripts\full_suite.txt`. **Résultat final : à compléter à la fin de l'exécution** (voir `16-resume-session.md`). Aucun résultat n'est déduit de l'avancement partiel ; aucun échec observé jusque-là (points `.` et `s` seulement).

## Limites
- Les tests PostgreSQL passent avec un rôle propriétaire/superuser local : ils prouvent la logique des politiques, pas leur effet avec le rôle d'exécution de production (BLOCKED_EXTERNAL).
- Les mocks de paiement ne prouvent pas le comportement des fournisseurs.
- `test_detect_user_language_falls_back_to_accept_language_header` : échec préexistant (voir rapport PR #20), non traité ici.

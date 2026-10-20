# ci-test-matrix.md — où chaque catégorie de tests s'exécute

Sources : `.github/workflows/ci.yml` de `main` au commit `78ab2b7` (lu via l'API GitHub), `.circleci/config.yml` et `.github/workflows/*.yml` de ma branche locale, journal du run n°202. Aucune de ces CI n'a été exécutée par moi sur ma branche (rien n'est poussé).

## 1. Situation de la branche par rapport à `main`
`git fetch origin` (lecture seule) : `origin/main` = `78ab2b7`, **44 commits d'avance** sur le point de départ de ma branche (`6619bc5`), ma branche a 11 commits propres. `git merge-tree --write-tree` (simulation, aucune modification) : **un seul conflit textuel prévisible, `api/services/evaluation_datasets.py`** ; 8 fichiers modifiés des deux côtés (`ci.yml`, `config.py`, `main.py`, `routers/evaluation_datasets.py`, `services/evaluation_datasets.py`, `tasks/celery_app.py`, `openapi.json`, `tests/conftest.py`). Les 7 autres se fusionnent sans conflit textuel, ce qui ne prouve pas qu'ils soient compatibles : à tester après intégration. **Rien n'a été fusionné.**
Conséquence pour les tests : `main` a supprimé les langues `de`, `es`, `pt`, `ar` (commit `9ba1aee`) ; l'échec i18n préexistant sur `de` est donc probablement sans objet sur `main` : à vérifier, non conclu.

## 2. GitHub Actions (`main` au commit `78ab2b7`)
| Job | Contenu | Durée max | Dernier résultat observé |
|---|---|---|---|
| `backend-tests` | `pytest -q -rfE --maxfail=20` + 7 `--ignore` ; service **PostgreSQL pgvector:pg16** (`rag_saas_test`), Redis 7, conteneur **MinIO** ; `ci_create_buckets.py` ; migrations Alembic | 75 min | run 202 : **6256 passés, 47 ignorés, 23 désélectionnés, 41 min 22 s** (succès) |
| `backend-security` | `pip-audit` (avec `--ignore-vuln PYSEC-2026-2447`) | 15 min | succès dans le même run (liste des jobs : succès global ; détail non relu) |
| `build-backend`, `build-frontend` | construction Docker / Next.js | 15 min | idem |
| `frontend-checks` | `npm ci`, `next typegen`, `tsc --noEmit`, `npm run lint`, `npm test` (Vitest), `npm audit --production` | 15 min | idem |
| `celery-worker.yml` | worker Celery en rafale toutes les 10 min avec les **secrets du dépôt** : ce n'est pas un test, c'est du traitement réel | n/a | hors périmètre test |
| `bandit.yml` | analyse statique, non bloquante | n/a | non lu |
Run n°181 (`6619bc5`, merge PR n°22) : échec ; n°202 (`78ab2b7`) : succès. La cause du n°181 n'a pas été relue ici (NOT_VERIFIED).
Point corrigé sur `main` avant ma reprise : l'ancien `backend-tests` utilisait le **secret `DATABASE_URL`, c'est-à-dire la vraie base**, et exportait aussi les secrets S3 / e-mail. Le commentaire de `main` le dit lui-même (« Until 2026-10-10 this job used the repository secret DATABASE_URL, i.e. the real database »). **Ma branche locale contient encore l'ancienne version** de ce job : tant que `main` n'est pas intégré, une CI lancée depuis ma branche réintroduirait ce risque. Ne pas pousser ma branche sans avoir intégré `main` d'abord. Je n'ai pas pu lire les secrets : ce que ces tests ont écrit dans la base visée avant le correctif est **NOT_VERIFIED** (à vérifier par la propriétaire : comptes `pg-integration-*@example.com`, `staging-idor-*@example.invalid` dans la base réelle).

## 2b. Job ajouté par ma branche (non poussé, jamais exécuté sur GitHub)
`backend-postgres-tests` (PostgreSQL 16 + pgvector, base `rag_ci_scratch`, chaîne Alembic puis aller-retour `0137`, puis les tests PostgreSQL destructifs avec la garde `disposable_pg_guard`). Il ajoute désormais `tests/test_postgres_system_log_handler.py`. Il **n'existe pas** dans `main` : dans `main`, les tests RLS / concurrence / `P0` sont ignorés (variables d'autorisation absentes) ; seul ce job les exécuterait en CI. Rejoué en local : 41 tests verts (historique). **Non exécuté sur GitHub : NOT_RUN.**

## 3. CircleCI (`.circleci/config.yml`, ma branche)
| Job | Contenu | Résultat connu |
|---|---|---|
| `api-tests` | 4 lots pytest séquentiels (fichiers nommés un à un), `--cov-fail-under=75`, PostgreSQL + Redis + MinIO + **worker Celery réel** + Tesseract/poppler + Node ; resource class `large` | vert sur `main` (observé plus tôt dans la session : `59d5ec9`) ; non relu pour `78ab2b7` |
| `rag-pipeline-regression` | garde de régression de la qualité de recherche (`tests/test_regression.py`) | non relu |
Les lots listent des fichiers un par un : un nouveau fichier de test n'y est exécuté que s'il y est ajouté. Mes nouveaux fichiers (`test_isolated_test_runner.py`, `test_postgres_system_log_handler.py`) ne sont **pas** listés dans les lots CircleCI (ils tournent dans le job GitHub qui prend tout `tests/`).

## 4. Matrice : catégorie → où elle tourne
| Catégorie | Local isolé (cette session) | GitHub `main` | CircleCI | Remarque |
|---|---|---|---|---|
| Tests unitaires (SQLite) | 84 vérifiés ; reste NOT_RUN | oui | oui | |
| Intégration PostgreSQL / RBAC / JWT / OAuth / SSL | historique seulement | oui (service pg16) | oui | |
| PostgreSQL destructifs : RLS, concurrence, `P0` | historique seulement | **non** (ignorés) | non | seul mon job non poussé les exécute |
| Worker Celery réel | `inspect ping` vérifié (07:12) ; tests e2e historiques | non (pas de worker) | oui | |
| Stockage S3 (MinIO) | historique | oui | oui | |
| OCR (Tesseract) | historique (18 passés) | non précisé | oui (installé) | |
| Facturation et webhooks (mockés) | dans la suite ; non rejoué ici | oui | oui | aucun fournisseur réel |
| Stripe / Paystack live | NOT_RUN_EXTERNAL_DEPENDENCY (8) | non | non | |
| OAuth tiers, Notion, Drive | NOT_RUN_EXTERNAL_DEPENDENCY (7) | non | non | |
| Staging hébergé | NOT_RUN_EXTERNAL_DEPENDENCY (12) | non | non | exige la base de staging |
| `network_flaky` (23, API GitHub publique) | historique (23 passés) | **désélectionnés** | non | aucune CI ne les exécute |
| 7 fichiers `--ignore` (75 tests) | NOT_RUN | **exclus** | exclus (comme CircleCI le documente) | |
| Frontend : `tsc`, ESLint, Vitest | non rejoués dans cette phase | oui (`frontend-checks`) | non | |
| Ruff | vérifié (code 0) | oui (dans `backend-tests`) | non | |

## 5. Propositions (non appliquées, pour décision)
1. Intégrer `main` dans la branche (ou rebaser) **avant** tout push, puis relire `ci.yml` : garder la version PostgreSQL / MinIO de `main` pour `backend-tests` et y adjoindre mon job `backend-postgres-tests`.
2. Job distinct, déclenché manuellement ou la nuit, pour les 23 tests `network_flaky` (avec un jeton GitHub pour sortir de la limite de 60 requêtes/h) : ils quittent la désélection silencieuse sans ralentir les PR.
3. Jobs pour les 7 fichiers exclus après les avoir passés une fois en local.
4. Lister `test_isolated_test_runner.py` et `test_postgres_system_log_handler.py` dans les lots CircleCI si CircleCI doit rester une validation indépendante.

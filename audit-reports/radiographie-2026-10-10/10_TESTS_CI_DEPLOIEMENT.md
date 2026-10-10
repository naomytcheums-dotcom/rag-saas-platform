# 10 — Tests, CI et déploiement

Audit du 2026-10-10, HEAD `59d5ec9`.

## 1. Tests découverts (mesure)
| Suite | Emplacement | Découverts | Méthode |
|---|---|---:|---|
| Backend pytest (collecte sur HEAD, mêmes `--ignore` que la CI) | `tests/`, `tests_pipeline/` | **6 130 collectés** (+23 désélectionnés = 6 153) | `pytest --collect-only -q`, 17 s ; **aucun test exécuté par cette commande** |
| dont tests à la racine de `tests/` | `tests/test_*.py` | 5 618 | décompte des lignes de collecte |
| dont `tests/backend/*` | ab-tests, analytics, autonomous, fine-tuning, media, whitelabel | 187 | idem |
| dont `tests/docs/` | liens / contrats de documentation | 316 (dont 294 dans `test_links.py`) | idem |
| dont `tests_pipeline/` | ingestion du prototype `src/` | 9 | idem |
| Fichiers de test Python (`test_*.py`) | `tests/` | 473 (467 contiennent au moins un test collecté) | `Get-ChildItem` / collecte |
| Frontend vitest | `frontend/**/*.test.ts(x)` | 27 fichiers | **178 tests** exécutés (voir §2) |
| SDK | `sdks/` (python, js, react, vue) | 7 fichiers de test | décompte de fichiers ; nombre de tests NON MESURÉ |
| Fichiers exclus de la CI | `sdks/python/tests/test_client.py`, `tests/test_agent.py`, `test_injection_test_set.py`, `test_integrations.py`, `test_regression.py`, `test_voice.py`, `tests_pipeline/test_retrieval.py` | — | `ci.yml` : tests du prototype legacy `src/` (dépendances non installées) ou nécessitant un navigateur ; **jamais exécutés par la CI** |

Les suites les plus fournies : `tests/docs/test_links.py` 294, `tests/test_documents.py` 255, `tests/test_auth_api.py` 174, `tests/test_p0_ssrf_outbound.py` 75, `tests/test_retrieval_config.py` 68, `tests/test_retrieval_pipeline.py` 65.

## 2. Résultats réellement observés
| Résultat | Source | Date | Détail |
|---|---|---|---|
| **EXÉCUTÉ dans cet audit** : `ruff check api` | local | 2026-10-10 | « All checks passed » |
| **EXÉCUTÉ dans cet audit** : `npx tsc --noEmit` (frontend) | local | 2026-10-10 | code de sortie 0 |
| **EXÉCUTÉ dans cet audit** : `npx eslint .` (frontend) | local | 2026-10-10 | code de sortie 0 |
| **EXÉCUTÉ dans cet audit** : `npx vitest run` | local | 2026-10-10 | **27 fichiers, 178 tests passés, 0 échec** (100 s) |
| **NON EXÉCUTÉ dans cet audit** : suite pytest backend | — | — | seule la collecte a été faite ; un run complet dure ~50-60 min et certains tests écrivent sur des services simulés |
| GitHub Actions `CI` sur `59d5ec9` (HEAD, push sur main) | distant, consulté via API publique | 2026-10-10 | **success** : `backend-tests` (42 min), `backend-security`, `build-backend`, `frontend-checks`, `build-frontend` ; nombre exact de tests non relevé |
| GitHub Actions `CI` sur `4ee2c22` | distant | 2026-10-10 | **success** |
| GitHub Actions `CI` sur `b8a0471` | distant | 2026-10-10 | **failure** : `backend-tests` 5 échecs / 6 021 passés / 46 ignorés / 23 désélectionnés (56 min 36 s) — corrigés ensuite (voir `15_METHODOLOGIE_ET_LIMITES.md` et la liste des commits `60dee60`…`4ee2c22`) |
| CircleCI `api-tests` sur `59d5ec9` (build #494) | distant | 2026-10-10 | **success**, 3 256 s ; lots affichés : 1 238 passés, 727 passés, 1 475 passés + 9 ignorés ; **couverture mesurée 77,41 %** (seuil 75 %) sur les lots de la liste fixe du job |
| CircleCI `rag-pipeline-regression` sur `59d5ec9` | distant | 2026-10-10 | **success** |
| CircleCI `api-tests` sur `4ee2c22` (build #490) | distant | 2026-10-10 | **failed** : conteneur MinIO tué (exit 137) ~5 min après le démarrage, puis 21 échecs + 13 erreurs tous « Could not connect to http://localhost:9000 » → **erreur d'infrastructure, pas de code** ; le build suivant sur `eb2e8e5` (#491) et sur main (#494) a réussi |
| Bandit (non bloquant) | distant | 2026-10-10 | success sur les commits récents ; **rapports non lus** |
| `backend-security` (pip-audit) | distant | 2026-10-10 | success avec `--ignore-vuln PYSEC-2026-2447` (diskcache 5.6.3, aucune version corrigée, dépendance transitive de `dspy`) ; l'outil n'a pas été lancé localement |
| Vercel | — | — | **STATUT DISTANT NON VÉRIFIÉ** (aucun accès, aucune configuration Vercel dans le dépôt) |

Preuves PostgreSQL (tests opt-in, base jetable locale uniquement, 2026-10-10) : concurrence abonnements (R4), crédits (BILL-011), factures (5 tests) : **réussis** avec garde `disposable_pg_guard` ; **non exécutés en CI**.

Tests ignorés connus (dernier décompte local élargi) : 22 = 8 tests « live » Stripe/Paystack (pas de clé), 9 `P0_PG_TEST_URL`, 5 concurrence PostgreSQL (opt-in).

## 3. Risques de tests qui passent sans prouver le comportement réel
- Base **SQLite** en mémoire pour presque toute la suite : verrous, RLS, FK, types vectoriels non vérifiés (voir `08_DATABASE_MIGRATIONS.md`).
- Fournisseurs simulés (Stripe, Paystack, S3, LLM, Resend, Redis dans plusieurs tests) : aucune preuve d'intégration réelle. Les tests « live » existent mais sont ignorés.
- Plusieurs tests dépendent du `.env` du développeur (corrigés pour 3 d'entre eux : clés Anthropic, OAuth) ; d'autres peuvent encore en dépendre : **NON DÉTERMINÉ**.
- `test_sales_models.py` : instable en local quand `RATE_LIMIT_REDIS_URL` pointe vers un Redis distant (timeouts) ; stable en CI (Redis local).
- La couverture 77,41 % mesure les **lignes de `api/`** exécutées par le sous-ensemble listé en dur dans `.circleci/config.yml` ; elle ne couvre pas les fichiers de test absents de cette liste (risque : nouveaux tests non ajoutés à la liste CircleCI ; la CI GitHub, elle, lance tout `tests/`).

## 4. Déploiement et exploitation (configuration ≠ disponibilité)
- `render.yaml` ne décrit **que** le prototype Streamlit (`nova-fastapi-assistant`, `./Dockerfile`, health check `/_stcore/health`). Le service API FastAPI (`Dockerfile.api`, `gunicorn.conf.py`, health `/health`, readiness `/health/ready`) est documenté dans `docs/deployment/RENDER.md` mais **n'est pas décrit par un blueprint** : sa configuration réelle vit dans le tableau de bord Render (NON VÉRIFIÉ). Selon l'utilisatrice, `WEB_CONCURRENCY=1` et `EMBEDDER_WARMUP_ON_STARTUP=false` y ont été posés.
- Aucun service Celery worker ni beat dans `render.yaml`. **`Dockerfile.api` lance uniquement `gunicorn`** : le worker embarqué (`docker-entrypoint.sh`) a été essayé puis **retiré** parce que le conteneur gratuit de 512 Mo devenait injoignable (commentaire du Dockerfile) ; le workflow `celery-worker.yml` exécute un worker/beat planifié par rafales de 420 s (GitHub Actions « scheduled burst », observé en succès). Donc **les tâches asynchrones et périodiques (ingestion, facturation, purge RGPD, beat) ne sont pas garanties en production** ; ce que la production exécute réellement n'est pas vérifiable depuis le dépôt.
- Aucun `alembic upgrade head` dans les fichiers de déploiement : exécution manuelle présumée (cohérent avec « je lance 0136 moi-même »).
- Frontend : Next.js 16 (`frontend/Dockerfile` lance `npm start`) ; hébergement Vercel annoncé par le cahier des charges mais **aucun fichier Vercel dans le dépôt** : NON VÉRIFIÉ.
- Sauvegardes, restauration, RPO/RTO, rollback : **non établis** dans les fichiers (un `docs/audit/BACKUP_AUDIT.md` existe, non repris ici).
- Observabilité : Prometheus/Grafana/Loki/Tempo/OTel (`observability/`), Sentry (frontend), `/metrics` : protégé par `METRICS_AUTH_TOKEN` **uniquement si cette variable est définie** (sinon public) ; alertes de production : non établies.
- Versions : API Docker `python:3.13-slim-bookworm`, CI Python 3.13, venv local 3.13.12 ; Bandit tourne en 3.11 ; **`agents.md` annonce Python 3.11** (documentation obsolète).

## 5. Distinction erreurs de code / infrastructure
- 5 échecs GitHub sur `b8a0471` : tous des causes **de test/CI** (clé Anthropic absente ×2, identifiants OAuth absents ×1, faux positif du scan de secrets ×1, chemin Windows en dur ×1) ; aucune régression applicative. Un 6ᵉ test (contrat « liens e-mailés → pages », `test_p1_frontend_link_contract.py`) a été trouvé en échec en local et mis à jour avant la CI.
- CircleCI #482/#484/#486 : dépassement de la limite de 60 min du job (infrastructure/durée) ; #490 : MinIO tué (infrastructure).

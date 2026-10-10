# 14 — Environnements et dépendances

Audit du 2026-10-10. **Noms de variables uniquement, aucune valeur.** Les fichiers `.env` / `.env.staging` n'ont pas été ouverts ; les noms viennent de `api/config.py`, `.env.example`, des workflows CI, de `render.yaml` et des sous-agents. Disponibilité réelle de chaque service : **NON VÉRIFIÉE**.

## Environnements identifiés
| Environnement | Configuration observée | État de vérification |
|---|---|---|
| Développement local | `.env` (ignoré), `docker-compose.yml` (prototype Streamlit + Chroma), `run_local_redis.py`, venv Python 3.13 | le `.env` local référence des services distants (pooler PostgreSQL, Redis Upstash) : risque d'exécuter des tests contre eux ; les tests de cet audit forcent une `DATABASE_URL` factice injoignable |
| Test | SQLite en mémoire (suite principale) ; PostgreSQL jetable local `rag-pr1-disposable-pg` pour les tests opt-in (garde `tests/disposable_pg_guard.py`) | vérifié le 2026-10-10 |
| CI GitHub Actions | `ci.yml` (PostgreSQL/Redis en service, placeholders OAuth, `COOKIE_SECURE=False`, secrets du dépôt pour le reste) | consulté : success sur HEAD |
| CI CircleCI | `.circleci/config.yml` (pgvector/pgvector:pg16, cimg/redis:7.4, bitnamilegacy/minio:2025.7.23, worker Celery en arrière-plan) | consulté : success sur HEAD |
| Staging | `.env.staging.example`, `scripts/staging_*`, tests `test_staging_*` ; base de staging via pooler | usage réel NON VÉRIFIÉ |
| Production | API Render (Docker, `Dockerfile.api`), PostgreSQL Supabase, Redis, frontend Vercel annoncé | **NON VÉRIFIÉ** ; `render.yaml` ne décrit que le prototype Streamlit |
| Auto-hébergé | `docker-compose.selfhosted.yml`, `install.sh`, `update.sh`, `uninstall.sh` ; `BILLING_ALLOW_SELF_SERVICE_PAID_PLANS`, `CREDITS_ALLOW_UNPAID_TOPUP` | non exécuté |

## Variables requises (sans valeur par défaut dans `api/config.py`)
`JWT_SECRET_KEY`, `SESSION_MIDDLEWARE_SECRET`, `AUDIT_LOG_HMAC_SECRET_KEY` (chargement de la configuration impossible sans elles) + une URL de base de données (`DATABASE_URL`, éventuellement `DATABASE_URL_TRANSACTION`).

## Variables opérationnelles (noms)
- Données : `DATABASE_URL`, `DATABASE_URL_TRANSACTION`, `REDIS_URL`, `RATE_LIMIT_REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `WEB_CONCURRENCY`, `EMBEDDER_WARMUP_ON_STARTUP`, `EMBEDDING_VECTOR_DIM`.
- Stockage : `S3_ENDPOINT_URL`, `S3_BUCKET_NAME`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_REGION`, `S3_PUBLIC_BASE_URL`, `S3_DOCUMENTS_BUCKET_NAME`, `S3_VOICE_BUCKET_NAME`.
- Sécurité : `ENCRYPTION_MASTER_KEY`, `SECRET_ENCRYPTION_KEY`, `JWT_PREVIOUS_SECRET_KEYS`, `COOKIE_SECURE`, `METRICS_AUTH_TOKEN`, `MCP_STDIO_ENABLED`, `CLAMAV_ENABLED`, `CLAMAV_HOST`.
- Fournisseurs : `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, autres clés LLM, `RESEND_API_KEY`, `EMAIL_FROM_ADDRESS`, `SUPPORT_EMAIL`, `STRIPE_SECRET_KEY`, `PAYSTACK_SECRET_KEY`, `GOOGLE_OAUTH_CLIENT_ID/SECRET`, `GITHUB_OAUTH_CLIENT_ID/SECRET`, Twilio, Airbyte (`AIRBYTE_API_URL`…).
- Facturation : `BILLING_ALLOW_SELF_SERVICE_PAID_PLANS`, `CREDITS_ALLOW_UNPAID_TOPUP`, `CREDITS_AUTO_REFILL`, `CREDIT_PACK_CURRENCY`, `BILLING_GRACE_PERIOD_DAYS`.
- Observabilité : `SENTRY_DSN`, `NEXT_PUBLIC_SENTRY_DSN`, `SENTRY_AUTH_TOKEN`, `SENTRY_ORG`, `SENTRY_PROJECT`, `PROMETHEUS_MULTIPROC_DIR`.
- Frontend : `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_ENVIRONMENT`, `NEXT_PUBLIC_SOCIAL_*`.
- Tests : `RAG_DISPOSABLE_PG_URL`, `RAG_DISPOSABLE_PG_CONFIRM`, `P0_PG_TEST_URL`.

Les valeurs de production, leur présence et leur cohérence (ex. `WEB_CONCURRENCY=1`, `EMBEDDER_WARMUP_ON_STARTUP=false` selon l'utilisatrice) ne sont **pas vérifiables depuis le dépôt**.

## Dépendances : déclarées / verrouillées / utilisées
- Python : `requirements-api.txt` (66 paquets épinglés, verrouillage par épinglage — pas de lockfile hash), `requirements-optional.txt` (8 paquets lourds : docling, deepeval, dspy, mem0ai, lightrag-hku, beeai-framework, presidio-analyzer, openlineage-python), `requirements.txt` (13, prototype legacy). **Comparaison avec les imports réels : NON FAITE** (aucun outil exécuté) — cette comparaison reste à faire.
- Node : `frontend/package.json` (13 + 17 dev), `package-lock.json` présent (régénéré compatible Docker par le commit de fusion de `main`).
- Dependabot : 15 branches `origin/dependabot/*` (références locales, non rafraîchies) : 5 GitHub Actions, 5 npm (jsdom, typescript 7.0.2, plugin-react, vitest 5.0.3, un lot), 5 pip (a2a-sdk, boto3, litellm 1.104, sqlalchemy 2.1.3, **stripe 16.0.0** — saut majeur depuis 11.4.1) ; **non évaluées**. Les mises à jour majeures (SQLAlchemy 2.1, TypeScript 7, Stripe 16) sont à risque de régression et doivent être testées avant tout merge (`agents.md` l'impose).
- Vulnérabilités connues : `pip-audit` en CI (1 exception diskcache). `npm audit` : NON EXÉCUTÉ.
- Incompatibilité documentaire : `agents.md` (Python 3.11) vs Dockerfile/CI (3.13) ; Bandit en 3.11.

## Services externes requis en production
PostgreSQL + pgvector (Supabase), Redis, S3/R2, un fournisseur LLM, Resend, Stripe et/ou Paystack, éventuellement ClamAV, Twilio, Airbyte, Sentry. Tous **NON VÉRIFIÉS** dans cet audit (aucun appel externe).

---
## Annexe — Exploration automatisée du déploiement (sous-agent, lecture seule)

<!-- ANNEXE_AJOUTEE -->
### Audit read-only — `C:\Users\NITROV15\Downloads\rag-saas-platform`

> Méthode : inventaire par `frontend/app/**/page.tsx` (74 fichiers trouvés), puis recherche des appels `api.*`/`fetch`, liens littéraux et variables d’environnement. Disponibilité réelle non testée : **NON VÉRIFIÉ**.

#### A. Déploiement / opérations

##### Configuration et cibles

| Élément | Configuration observée |
|---|---|
| API production documentée | Render Web Service `rag-saas-api`, Docker, plan gratuit — `docs/deployment/RENDER.md` |
| Blueprint actuel | `render.yaml:4-17` définit toutefois `nova-fastapi-assistant`, construit `./Dockerfile`, health check `/_stcore/health`, donc le prototype Streamlit, pas l’API FastAPI |
| API Docker | `Dockerfile.api:...` lance `gunicorn -c gunicorn.conf.py api.main:app` |
| Prototype Streamlit | `Dockerfile:...` lance `streamlit run dashboard/app.py --server.port=8501` |
| Frontend | Next.js ; `frontend/Dockerfile:...` lance `npm start`. Aucun service Vercel identifié dans les fichiers examinés |
| Base de données | PostgreSQL/Supabase décrit dans `docs/deployment/RENDER.md`; URL `DATABASE_URL` |
| Redis | Redis/Upstash pour rate limiting et Celery (`RATE_LIMIT_REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`) |
| Local/dev | `docker-compose.yml:1-31`, prototype Streamlit sur `8501`, volume Chroma persistant |
| Self-hosted/observability | `docker-compose.selfhosted.yml`, `docker-compose.observability.yml`, Prometheus/Grafana/Loki/Tempo/OTel sous `observability/` |

**Statut de configuration ≠ disponibilité réelle.** La documentation affirme des vérifications Render datées du 2026-09-17, mais cet audit n’a effectué aucun appel réseau : état actuel **NON VÉRIFIÉ**.

##### Commandes et health checks

- API : Gunicorn, `0.0.0.0:8000`, `WEB_CONCURRENCY` par défaut `4`, timeout `130 s` — `gunicorn.conf.py:26-31`.
- API Docker health check : `GET /health`, intervalle 30 s, timeout 5 s, start period 20 s — `Dockerfile.api`.
- API readiness documentée : `GET /health/ready`, contrôle notamment DB et Redis — `docs/deployment/RENDER.md`.
- Streamlit health check : `/_stcore/health`, port 8501, start period 40 s — `Dockerfile`.
- L’entrypoint `docker-entrypoint.sh:1-20` démarre un worker Celery puis Gunicorn dans le même conteneur.
- `render.yaml` ne déploie **ni service Celery worker ni Celery beat** (`render.yaml:4-17`). Le workflow GitHub `celery-worker.yml` exécute seulement un worker planifié par bursts — `.github/workflows/celery-worker.yml`.

##### Migrations

- `alembic.ini` est copié dans l’image API (`Dockerfile.api`).
- Aucun `alembic upgrade head` n’est visible dans `render.yaml`, `Dockerfile.api` ou `docker-entrypoint.sh`.
- Conclusion : les migrations ne sont pas exécutées automatiquement par le déploiement Render d’après les fichiers examinés. Responsable de l’exécution en production : **non établi**.

##### Variables d’environnement

Variables obligatoires sans valeur par défaut identifiées dans `api/config.py` :

- `JWT_SECRET_KEY` — `api/config.py:...`
- `SESSION_MIDDLEWARE_SECRET` — `api/config.py:...`
- `AUDIT_LOG_HMAC_SECRET_KEY` — `api/config.py:...`

Variables opérationnelles/configuration référencées :

- `DATABASE_URL`
- `REDIS_URL`/`RATE_LIMIT_REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `WEB_CONCURRENCY`
- `PROMETHEUS_MULTIPROC_DIR`
- `SENTRY_DSN`, `SENTRY_AUTH_TOKEN`, `SENTRY_ORG`, `SENTRY_PROJECT`
- fournisseurs LLM et intégrations (noms présents dans la configuration et les exemples d’environnement)
- `CLAMAV_ENABLED`, `CLAMAV_HOST`
- `GOOGLE_SERVICE_ACCOUNT_FILE`, `GOOGLE_CALENDAR_ID`, `GOOGLE_SHEET_ID`, `ANTHROPIC_API_KEY` — `render.yaml:10-17`

Frontend :

- `NEXT_PUBLIC_API_URL` — `frontend/lib/api.ts`, `frontend/app/dashboard/api-docs/page.tsx`
- `NEXT_PUBLIC_SENTRY_DSN`, `NEXT_PUBLIC_ENVIRONMENT` — `frontend/instrumentation.ts`, `frontend/instrumentation-client.ts`
- `NEXT_PUBLIC_SOCIAL_FACEBOOK`, `NEXT_PUBLIC_SOCIAL_X`, `NEXT_PUBLIC_SOCIAL_INSTAGRAM`, `NEXT_PUBLIC_SOCIAL_TIKTOK` — `frontend/components/figma/SocialLinks.tsx`

Les variables disposant de `??` ou de valeurs par défaut sont optionnelles côté frontend. Les valeurs sensibles ne sont pas reproduites.

##### Workers, mémoire et risques déduits

- `docker-entrypoint.sh:4-18` lance Celery et Gunicorn dans le même conteneur, worker `solo`, concurrence 1.
- Le script indique lui-même un risque de dépassement des 512 MB avec Gunicorn + Celery + Torch/sentence-transformers/OpenCV : **risque déduit**.
- Absence de worker persistant dans `render.yaml` : les tâches asynchrones peuvent rester en attente ; **risque déduit**.
- `gunicorn.conf.py:29-31` corrige le timeout SSE à 130 s ; sans cette configuration, les réponses de streaming dépasseraient le timeout standard de Gunicorn.
- Quatre workers par défaut avec dépendances ML lourdes : **risque déduit** de cold start/mémoire.
- Le plan Render gratuit implique un risque de cold start ; **risque déduit**, non mesuré.

##### Observabilité, sauvegardes, rollback

- Prometheus/Grafana/Loki/Tempo/OTel sont configurés sous `observability/`.
- Endpoint métriques exposé et lié depuis l’UI admin : `frontend/app/admin/page.tsx` (`/metrics`).
- Sentry configuré côté frontend et build Next.js : `frontend/next.config.ts`, `frontend/instrumentation*.ts`.
- CI/observabilité opérationnelle et alertes production : configuration complète non établie.
- Procédure de sauvegarde/restauration PostgreSQL, stratégie de rollback et RPO/RTO : **non établie dans les fichiers examinés**.
- `docker-compose.yml` persiste Chroma via `chroma-data`; cela ne constitue pas une sauvegarde.

##### CI

- `.github/workflows/ci.yml` :
  - tests backend `pytest`, timeout job 75 min ;
  - services PostgreSQL/Redis ;
  - lint frontend `npm run lint` ;
  - plusieurs jobs complémentaires avec timeout 15 min.
- `.github/workflows/bandit.yml` : analyse Bandit.
- `.github/workflows/celery-worker.yml` : worker + beat planifiés, fenêtre d’exécution bornée à 420 s, job timeout 12 min.
- `.circleci/config.yml` : pipeline historique avec PostgreSQL/Redis/MinIO et migrations ; statut d’usage actuel non établi.
- Tests frontend présents dans `frontend/**/*.test.tsx` et `frontend/**/*.test.ts`.

Points potentiellement instables : tests ML/intégration longs, worker GitHub non persistant, limites mémoire Render, pool PostgreSQL partagé, et divergence entre `render.yaml` et la documentation Render.

---


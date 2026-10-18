# Railway

Three services from this repository (same image, `Dockerfile.api`), each pointed at its own config file (Service -> Settings -> "Config as code" -> file path):

| Service | Config file | Notes |
|---|---|---|
| api | `deploy/railway/railway.api.json` | gunicorn, health check `GET /health` |
| worker | `deploy/railway/railway.worker.json` | `startCommand` = Celery worker, **no** health check (it does not listen on HTTP; a health check would fail every deployment) |
| beat | `deploy/railway/railway.beat.json` | `startCommand` = Celery beat, `numReplicas` 1, `overlapSeconds` 0 so two beats never overlap during a deployment |

All three share the same variables: the environment contract of `deploy/README.md` (`DATABASE_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`,
`RATE_LIMIT_REDIS_URL`, `JWT_SECRET_KEY`, `SESSION_MIDDLEWARE_SECRET`, `AUDIT_LOG_HMAC_SECRET_KEY`, `SUPPORT_EMAIL`, `ENCRYPTION_MASTER_KEY`, `SECRET_ENCRYPTION_KEY`).
Use Railway shared variables so they are set once. Add the Railway Redis plugin and reference it for the three Redis URLs (`${{Redis.REDIS_URL}}`
and a `/N` database suffix); a Redis reached over the public proxy must be `rediss://` with a password, the API refuses to start otherwise.
Use an external PostgreSQL with pgvector (for example Supabase) and run `alembic upgrade head` once, by hand, after a backup.

Status: the three files validate against Railway's published JSON schema (`tests/fixtures/deploy/railway.schema.json`, checked by
`tests/test_deploy_artifacts.py`); the container they start is the one built and run by `tests/test_deploy_dedicated_tenant_e2e.py`. Not deployed (no Railway account).

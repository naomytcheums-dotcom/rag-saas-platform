# Deployment targets

The API image is `Dockerfile.api` (gunicorn on port 8000, health check `GET /health`, readiness `GET /health/ready`). Background work (document
ingestion, scheduled billing, GDPR purges, evaluation jobs) needs a **Celery worker** and **one Celery beat**:

```
celery -A api.tasks.celery_app worker --loglevel=info
celery -A api.tasks.celery_app beat   --loglevel=info --schedule=/tmp/celerybeat-schedule      # exactly one instance
```

## Environment contract (every target, API + worker + beat)

Found by running the stack (not by reading it): the first versions of these files set a bare `REDIS_URL`, which the application never reads (its Redis
settings are the four below, defaulting to `localhost`), and omitted three settings without which the API refuses to start. `tests/test_deploy_artifacts.py`
now fails if a target forgets one of them.

| Variable | Meaning |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://...` PostgreSQL with the `vector` extension |
| `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `RATE_LIMIT_REDIS_URL` | Redis URLs (databases 0, 1, 2 by convention); `CACHE_REDIS_URL` (database 3) is optional |
| `JWT_SECRET_KEY`, `SESSION_MIDDLEWARE_SECRET`, `AUDIT_LOG_HMAC_SECRET_KEY` | three distinct random secrets, required at start |
| `SUPPORT_EMAIL` | required at start (not a secret) |
| `ENCRYPTION_MASTER_KEY` | AES-256 key (urlsafe base64 of 32 random bytes) for stored secrets; without it webhooks / connectors / MCP credentials cannot be saved. **Losing it makes them unreadable.** |
| `SECRET_ENCRYPTION_KEY` | Fernet key (same format) for signing keys, SSO client secrets, BYOK LLM keys, chat tokens, DKIM keys |
| `COOKIE_SECURE=true`, `CREDITS_ALLOW_UNPAID_TOPUP=false` | production values (set in each file) |

A Redis reached over the public internet must be `rediss://` with a password: the API refuses to start otherwise (private single-label, `.internal`,
`.svc`, `.local` and private-address hosts are exempt, `ALLOW_INSECURE_BROKER=1` overrides on purpose). Generate keys with
`python -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"`. Run `alembic upgrade head` once, by hand, after a backup.

## Targets and what was actually executed

| Target | Files | Executed locally | Not executed (needs an account) |
|---|---|---|---|
| Dedicated tenant / dedicated database / private / on-premise / VPC | `deploy/dedicated-tenant/`, `docs/deployment/PRIVATE_ONPREM_VPC.md` | image built from `Dockerfile.api`, `docker compose up --wait` (db, redis, api, worker, beat healthy), `alembic upgrade head`, `/health`, `/health/ready`, register + login, two tenants side by side proven isolated, no database / Redis port published, offline start: `tests/test_deploy_dedicated_tenant_e2e.py` | nothing cloud-specific |
| AWS | `terraform/aws` (ECS Fargate: api + ALB, worker, beat) | `terraform fmt -check`, `init -backend=false`, `validate` (hashicorp/terraform 1.9, aws ~> 5.0) | `plan` / `apply` |
| GCP | `terraform/gcp` (Cloud Run API; worker/beat on GKE or a VM, see the file header) | same, google ~> 5.0 | `plan` / `apply` |
| Azure | `terraform/azure` (Container Apps: api, worker, beat) | same, azurerm ~> 3.100 | `plan` / `apply` |
| Kubernetes | `kubernetes/rag-saas.yaml` | `kubeconform -strict` (1.30) | `kubectl apply` on a cluster |
| Helm | `helm/rag-saas/` | `helm lint`, `helm template` (default and ingress on) + `kubeconform -strict` | `helm install` on a cluster |
| Railway | `railway/railway.{api,worker,beat}.json` | validated against Railway's published JSON schema | deployment |
| Fly.io | `fly/fly.toml` | parsed; keys and process groups checked by `tests/test_deploy_artifacts.py` | `flyctl config validate` (needs a token), deployment |
| DigitalOcean | `terraform/digitalocean/app.yaml` | validated against the DigitalOcean API's published App Spec schema | `doctl apps spec validate`, deployment |
| Render | `render/render.api.yaml` | parsed; environment contract checked | blueprint launch |

The commands are in `docs/project-handover/e2e_evidence/infra_RESUME.md`; the checks that do not need Docker run in the normal test suite.
Nothing here was deployed to a real cloud.

# Deployment targets

The API image is `Dockerfile.api` (gunicorn on port 8000, health check `GET /health`, readiness `GET /health/ready`). Background work (document
ingestion, scheduled billing, GDPR purges, evaluation jobs) needs a **Celery worker** and **one Celery beat**:

```
celery -A api.tasks.celery_app worker --loglevel=info
celery -A api.tasks.celery_app beat   --loglevel=info      # exactly one instance
```

| Target | Files | Status |
|---|---|---|
| Docker Compose | `docker-compose.yml`, `docker-compose.selfhosted.yml` | pre-existing |
| Render | `deploy/render/render.api.yaml` (API + worker + beat blueprint; the root `render.yaml` is the old prototype and is left untouched) | written, not applied |
| Railway | `deploy/railway/` | written, not deployed |
| Fly.io | `deploy/fly/fly.toml` | written, not deployed |
| Kubernetes | `deploy/kubernetes/` | written, not applied |
| Helm | `deploy/helm/rag-saas/` | written, not linted (helm not installed on the authoring machine) |
| Terraform | `deploy/terraform/{aws,gcp,azure,digitalocean}` | written, not validated (terraform not installed on the authoring machine) |
| Dedicated tenant | `deploy/dedicated-tenant/` | written, not run |

**Honest status:** none of these files has been executed against a real cloud account. They follow each platform's documented format and the
real container contract above, and every one needs secrets (see `.env.example` / `docs/deployment`) and a first `alembic upgrade head`
(run once, by the owner, against the target database after a backup). Treat them as a starting point to be validated on a staging account.

# Docker

Three compose files, for different purposes:

| File | Purpose |
|---|---|
| `docker-compose.yml` | local development |
| `docker-compose.selfhosted.yml` | production self-hosted deployment — used by `install.sh`/`update.sh`/`uninstall.sh` |
| `docker-compose.observability.yml` | optional local observability stack (see [Observability Stack](OBSERVABILITY_STACK.md)) |

## Services (`docker-compose.selfhosted.yml`)

- `postgres` — the database, with a named volume (`postgres-data`) so
  data survives container recreation.
- `redis` — Celery broker/result backend, named volume `redis-data`.
- `api` — the FastAPI backend.
- `celery-worker` — background job processing.
- `celery-beat` — scheduled tasks (reindexing, fine-tuning job polling,
  domain verification, backups).
- `frontend` — the Next.js dashboard.

## Common commands

```bash
# start
docker compose -f docker-compose.selfhosted.yml up -d

# logs
docker compose -f docker-compose.selfhosted.yml logs -f api

# run a one-off command inside the api container
docker compose -f docker-compose.selfhosted.yml exec -T api python -m alembic upgrade head

# stop
docker compose -f docker-compose.selfhosted.yml down
```

For local development instead of a production deployment, use the plain
`docker-compose.yml`.

## Data persistence

`postgres-data` and `redis-data` are named volumes — they survive
`docker compose down` (without `-v`) and container rebuilds. Only
`./uninstall.sh --purge-data` removes them deliberately — see
[Uninstall](UNINSTALL.md).

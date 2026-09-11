# Selling as self-hosted

## Real gap found and fixed first

This repo had **no containerization for the actual product** before
this part — its only `Dockerfile`/`docker-compose.yml` build an
unrelated, earlier Streamlit prototype ("nova"). Added for real:
`Dockerfile.api` (the FastAPI backend), `frontend/Dockerfile` (Next.js),
and `docker-compose.selfhosted.yml` (api + postgres + redis +
celery-worker + celery-beat + frontend, no managed Supabase/Upstash
dependency required).

## Install (1 command)

```bash
./install.sh
```

First run copies `.env.example` to `.env` (with a real, randomly
generated `SESSION_MIDDLEWARE_SECRET`) and stops so you can fill in the
rest (`RESEND_API_KEY`, `POSTGRES_PASSWORD`, a real `LICENSE_KEY` if
one was issued to you). Run it again to actually build, start every
container, wait for Postgres, run migrations, and validate the license.

## Offline license

`POST /license/generate` (superadmin) issues a real key
(`XXXX-XXXX-XXXX-XXXX`, cryptographically random). `POST
/license/validate` (public — a fresh install with no logged-in user yet
can still check its own key) is read-only and safe to call repeatedly
(e.g. on every startup). `POST /organizations/{org_id}/license/activate`
consumes one real activation slot (`max_activations`) — real,
honest error at the limit (`400`), not a silent bypass.

## Updates

No auto-update daemon — real, deliberate scope: `git pull && ./install.sh`
rebuilds the changed image(s) and re-runs migrations, which is the
correct way to apply a real code change to a self-hosted deployment
under version control (an auto-updater that pulls arbitrary code
without operator review is a real security liability for an air-gapped
or trust-sensitive deployment, not a convenience worth the risk here).

## Backup / restore

```bash
./scripts/backup.sh [dir]      # real pg_dump, gzip'd, timestamped
./scripts/restore.sh <file>    # real pg_restore, asks for confirmation first
```

## Air-gapped

Build the images once with network access
(`docker compose -f docker-compose.selfhosted.yml build`), `docker save`
them, transfer, `docker load` on the air-gapped host, then
`docker compose -f docker-compose.selfhosted.yml up -d` (no build step
needed there). License validation (`POST /license/validate`) is a
local-only check against this deployment's own Postgres — no outbound
call to any license server, by design, for exactly this environment.

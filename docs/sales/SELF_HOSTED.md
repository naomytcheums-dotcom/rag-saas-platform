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

## Updates (Partie 18: real rollback path)

```bash
./update.sh
```

Takes a real `pg_dump` backup first, then `git pull --ff-only`,
rebuilds the changed image(s), and re-runs migrations. If the rebuild
or the migration fails, it stops and tells you exactly which backup
file to restore from (`./scripts/restore.sh <file>`) — your data is
never left in an ambiguous state. Still no auto-update daemon — real,
deliberate scope: an updater that pulls arbitrary code without operator
review is a real security liability for an air-gapped or
trust-sensitive deployment, not a convenience worth the risk here.

## Uninstall (Partie 18)

```bash
./uninstall.sh              # stops and removes containers -- .env, backups/, and your database volume are untouched
./uninstall.sh --purge-data # also permanently deletes the database volume
```

## Backup / restore

```bash
./scripts/backup.sh [dir]      # real pg_dump, gzip'd, timestamped
./scripts/restore.sh <file>    # real pg_restore, asks for confirmation first
```

## License re-validation (Partie 18)

`api/tasks/sales.py`'s `validate_licenses` Celery task runs daily and
flips any `License` past its own real `expires_at` to `expired` — so a
deployment that never explicitly calls `/license/validate` again after
activation (a real, expected pattern for an air-gapped install) still
gets an honest, current status rather than staying reported `active`
indefinitely. Set `LICENSE_KEY` in `.env` to this deployment's own key
if you want other tooling to reference it directly (this setting is
not itself read by the validate/activate endpoints, which already work
against the real `License` row regardless).

## Air-gapped

Build the images once with network access
(`docker compose -f docker-compose.selfhosted.yml build`), `docker save`
them, transfer, `docker load` on the air-gapped host, then
`docker compose -f docker-compose.selfhosted.yml up -d` (no build step
needed there). License validation (`POST /license/validate`) is a
local-only check against this deployment's own Postgres — no outbound
call to any license server, by design, for exactly this environment.

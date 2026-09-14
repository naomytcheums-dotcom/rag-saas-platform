# Database Setup

## Managed (Docker Compose)

If you're using `docker-compose.selfhosted.yml` (via `install.sh`), the
`postgres` service is provisioned automatically and migrations run for
you on install/update. Nothing further to do — see [Docker](DOCKER.md).

## External / managed Postgres (e.g. Supabase)

Set `DATABASE_URL` in `.env` to your instance, using the `asyncpg`
driver:

```
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/dbname
```

Then run migrations:

```bash
cd api
alembic upgrade head
```

## Row-level security

Most tenant-scoped tables enable RLS as a second enforcement layer
beyond application checks — this is set up by the migrations
themselves, nothing extra to configure. See
[`docs/security/PARTIE_10_SECURITY.md`](../security/PARTIE_10_SECURITY.md).

## Extensions

If your Postgres provider doesn't enable extensions by default, ensure
`pgvector` (used for embedding storage/similarity search) is available
before running migrations.

## Verifying

```bash
alembic current
```

Should report the latest migration (`0108` as of the fine-tuning part —
check `api/alembic/versions/` for the current head).

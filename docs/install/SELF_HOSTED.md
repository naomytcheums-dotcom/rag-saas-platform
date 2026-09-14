# Self-hosted

Full detail on the self-hosted sales/deployment model is in
[`docs/sales/SELF_HOSTED.md`](../sales/SELF_HOSTED.md). This page
covers the actual installation steps.

## Requirements

Docker Engine + Docker Compose v2. See
[System Requirements](SYSTEM_REQUIREMENTS.md) for resource sizing.

## Install

```bash
./install.sh
```

First run copies `.env.example` to `.env`, generates a real random
`SESSION_MIDDLEWARE_SECRET`, and stops — asking you to fill in
`DATABASE_URL`, `RESEND_API_KEY`, and a license key. See
[Environment Variables](ENVIRONMENT.md) for the full list.

Second run (after `.env` is filled in) starts the stack via
`docker-compose.selfhosted.yml`, waits for Postgres to become healthy,
and runs Alembic migrations automatically.

## Upgrading

```bash
./update.sh
```

Takes a real backup first (`scripts/backup.sh`), pulls the latest code,
rebuilds, and migrates — with a rollback path documented on failure.
See [Upgrading](UPGRADING.md) and [Backup & Restore](BACKUP_AND_RESTORE.md).

## Uninstalling

```bash
./uninstall.sh            # stops and removes containers/network only
./uninstall.sh --purge-data   # also deletes the Postgres volume and backups
```

`--purge-data` is opt-in and explicit — a plain uninstall never deletes
your `.env`, backups, or database volume. See [Uninstall](UNINSTALL.md).

## Next steps

[Database Setup](DATABASE_SETUP.md),
[SSL & Domains](SSL_AND_DOMAINS.md),
[Observability Stack](OBSERVABILITY_STACK.md).

# Backup & Restore

## Backing up

```bash
./scripts/backup.sh
```

Runs a real `pg_dump` via
`docker compose -f docker-compose.selfhosted.yml exec -T postgres
pg_dump ...`, gzipped, written to a backup file. `./update.sh` runs
this automatically before every upgrade — see [Upgrading](UPGRADING.md).

## Restoring

```bash
./scripts/restore.sh <backup-file.sql.gz>
```

This **overwrites the current database** with the contents of the
backup file — it prompts for confirmation (Ctrl+C to cancel, Enter to
continue) before proceeding, since it's destructive.

```bash
gunzip -c "$FILE" | docker compose -f docker-compose.selfhosted.yml \
  exec -T postgres psql -U "$POSTGRES_USER" "$POSTGRES_DB"
```

## Backup retention

Backups accumulate under wherever `scripts/backup.sh` writes them (check
the script's output for the exact path) — this repository doesn't
automatically prune old backups, so set up your own retention/rotation
if disk space is a concern.

## Object storage

`pg_dump` covers the database only. Documents, media, and fine-tuning
datasets live in S3-compatible object storage and are not included in
this backup — back up your object storage bucket separately according
to your provider's own tooling.

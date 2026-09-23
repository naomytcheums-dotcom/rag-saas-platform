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

`scripts/backup.sh` prunes its own local backups older than
`BACKUP_RETENTION_DAYS` (default 30, set to `0` to disable). This only
covers files under `$BACKUP_DIR` on this host — if you copy backups
elsewhere (object storage, another host), that copy's own retention is
still yours to manage.

## Scheduling

This repository doesn't run `backup.sh` on a schedule itself (a
self-hosted deployment's own host is where a cron job belongs, not
something this platform can centrally trigger for you). A real,
minimal daily cron entry:

```cron
0 3 * * * cd /path/to/rag-saas-platform && ./scripts/backup.sh >> /var/log/rag-saas-backup.log 2>&1
```

`./update.sh` also runs a backup once automatically before every
upgrade regardless of this schedule — see [Upgrading](UPGRADING.md).

## Object storage

`pg_dump` covers the database only. Documents, media, and fine-tuning
datasets live in S3-compatible object storage and are not included in
this backup — back up your object storage bucket separately according
to your provider's own tooling.

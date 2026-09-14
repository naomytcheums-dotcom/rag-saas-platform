# Upgrading

## Self-hosted

```bash
./update.sh
```

What it actually does, in order:

1. Takes a real backup via `scripts/backup.sh` first — the update
   script refuses to skip this step.
2. `git pull --ff-only`.
3. Rebuilds and restarts the stack.
4. Runs Alembic migrations.
5. On any failure past the backup step, tells you exactly which backup
   file to restore from (`./scripts/restore.sh <backup_file>`) rather
   than leaving you to figure it out.

See [Backup & Restore](BACKUP_AND_RESTORE.md) for the restore path.

## Before upgrading

- Read the relevant entries in [`CHANGELOG.md`](../../CHANGELOG.md) for
  anything that needs manual attention (new required environment
  variables, breaking config changes).
- Confirm you have enough disk space for a new backup.

## SaaS

Managed upgrades are handled for you — no action required. See
[SaaS](SAAS.md).

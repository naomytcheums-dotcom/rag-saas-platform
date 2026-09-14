# Uninstall

```bash
./uninstall.sh
```

Stops and removes the containers and network
`docker-compose.selfhosted.yml` created. It deliberately does **not**
touch `.env`, your `backups/` directory, or Postgres's named data
volume — an uninstall that silently deletes real data is the one
mistake this script is written to avoid.

## Removing data too

```bash
./uninstall.sh --purge-data
```

Only with this explicit flag does uninstall also remove the Postgres
volume and backups. There is no prompt-based confirmation — the flag
itself is the confirmation, so don't pass it unless you mean it.

## Before purging

If you might reinstall later, take a fresh backup first regardless of
whether `--purge-data` already implies backups will be removed:

```bash
./scripts/backup.sh
```

See [Backup & Restore](BACKUP_AND_RESTORE.md).

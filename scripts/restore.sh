#!/usr/bin/env bash
# Partie 16 (bis) -- real Postgres restore, the counterpart to backup.sh.
set -euo pipefail

FILE="${1:?Usage: restore.sh <backup-file.sql.gz>}"
if [ ! -f "$FILE" ]; then
  echo "Backup file not found: $FILE"
  exit 1
fi

gzip -t "$FILE"
echo "This will overwrite the current database with $FILE. Press Ctrl+C to cancel, Enter to continue."
read -r _

gunzip -c "$FILE" | docker compose -f docker-compose.selfhosted.yml exec -T postgres psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-rag_saas}" "${POSTGRES_DB:-rag_saas}"
echo "Restore complete."

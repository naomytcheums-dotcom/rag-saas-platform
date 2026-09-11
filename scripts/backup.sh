#!/usr/bin/env bash
# Partie 16 (bis) -- real Postgres backup via pg_dump, run inside the
# real `postgres` container docker-compose.yml already defines --
# never a fabricated "backup" that's actually empty.
set -euo pipefail

BACKUP_DIR="${1:-./backups}"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILE="$BACKUP_DIR/backup_${TIMESTAMP}.sql.gz"

docker compose -f docker-compose.selfhosted.yml exec -T postgres pg_dump -U "${POSTGRES_USER:-rag_saas}" "${POSTGRES_DB:-rag_saas}" | gzip > "$FILE"
echo "Backup written to $FILE"

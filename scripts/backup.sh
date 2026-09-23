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

# Phase 5, Étape 7 -- real retention pruning (spec section 3.6, "30
# jours" default), opt-out via BACKUP_RETENTION_DAYS=0. Deliberately
# local-only, same honest scope as the rest of this script: this prunes
# files under $BACKUP_DIR on THIS host, not any object-storage copy you
# make of them yourself (see docs/install/BACKUP_AND_RESTORE.md).
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
if [ "$RETENTION_DAYS" -gt 0 ]; then
    find "$BACKUP_DIR" -name "backup_*.sql.gz" -mtime "+${RETENTION_DAYS}" -delete
fi

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

# Phase 5, Étape 22 -- real, optional S3/R2 upload (spec section 3.6).
# Off by default (BACKUP_S3_ENABLED=false or BUCKET unset) so this
# script still works on a bare local dev machine with no cloud creds.
# Uses the same S3_* env vars every other storage path in this codebase
# already uses (see .env.example).
BACKUP_S3_ENABLED="${BACKUP_S3_ENABLED:-false}"
BACKUP_S3_BUCKET="${BACKUP_S3_BUCKET:-${S3_BUCKET_NAME:-}}"
BACKUP_S3_PREFIX="${BACKUP_S3_PREFIX:-backups}"

if [ "$BACKUP_S3_ENABLED" = "true" ] && [ -n "$BACKUP_S3_BUCKET" ]; then
    if ! command -v aws >/dev/null 2>&1; then
        echo "WARNING: BACKUP_S3_ENABLED=true but 'aws' CLI not found -- skipping upload" >&2
    else
        S3_KEY="${BACKUP_S3_PREFIX}/$(basename "$FILE")"
        if aws s3 cp "$FILE" "s3://${BACKUP_S3_BUCKET}/${S3_KEY}" \
            ${S3_ENDPOINT_URL:+--endpoint-url "$S3_ENDPOINT_URL"}; then
            echo "Backup uploaded to s3://${BACKUP_S3_BUCKET}/${S3_KEY}"

            # Real, remote retention: prune S3 objects older than
            # RETENTION_DAYS, same window as the local prune above.
            if [ "$RETENTION_DAYS" -gt 0 ]; then
                CUTOFF_DATE=$(date -d "-${RETENTION_DAYS} days" +%Y-%m-%d 2>/dev/null || date -v-"${RETENTION_DAYS}"d +%Y-%m-%d 2>/dev/null || "")
                if [ -n "$CUTOFF_DATE" ]; then
                    aws s3 ls "s3://${BACKUP_S3_BUCKET}/${BACKUP_S3_PREFIX}/" \
                        ${S3_ENDPOINT_URL:+--endpoint-url "$S3_ENDPOINT_URL"} \
                        | awk '{print $1, $4}' | while read -r obj_date obj_name; do
                        if [ -n "$obj_date" ] && [ "$obj_date" \< "$CUTOFF_DATE" ]; then
                            aws s3 rm "s3://${BACKUP_S3_BUCKET}/${BACKUP_S3_PREFIX}/${obj_name}" \
                                ${S3_ENDPOINT_URL:+--endpoint-url "$S3_ENDPOINT_URL"}
                        fi
                    done
                fi
            fi
        else
            echo "WARNING: failed to upload backup to S3/R2" >&2
        fi
    fi
else
    echo "S3/R2 upload skipped (BACKUP_S3_ENABLED=$BACKUP_S3_ENABLED, bucket=${BACKUP_S3_BUCKET:-unset})"
fi

#!/usr/bin/env bash
# Partie 18 -- self-hosted update, with a real rollback path: takes a
# real backup before touching anything, pulls/rebuilds, migrates, and
# on any failure past that point tells the operator exactly which
# backup file to restore from -- never leaves them guessing.
set -euo pipefail

COMPOSE_FILE="docker-compose.selfhosted.yml"

if [ ! -f .env ]; then
  echo ".env not found -- run ./install.sh first."
  exit 1
fi

echo "Taking a real backup before updating..."
BACKUP_FILE=$(./scripts/backup.sh | sed -n 's/^Backup written to //p')
echo "Backup saved: $BACKUP_FILE (restore with: ./scripts/restore.sh $BACKUP_FILE)"

echo "Pulling latest code (git pull)..."
git pull --ff-only

echo "Rebuilding and restarting the application stack..."
if ! docker compose -f "$COMPOSE_FILE" up -d --build; then
  echo "Rebuild/restart failed. Your data is unchanged -- backup is at $BACKUP_FILE if you need it."
  exit 1
fi

echo "Waiting for Postgres to become healthy..."
until docker compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U "${POSTGRES_USER:-rag_saas}" &> /dev/null; do sleep 2; done

echo "Running database migrations..."
if ! docker compose -f "$COMPOSE_FILE" exec -T api python -m alembic upgrade head; then
  echo "Migration failed. Restore the pre-update backup with: ./scripts/restore.sh $BACKUP_FILE"
  exit 1
fi

echo ""
echo "Update complete. The API is at http://localhost:8000, the frontend at http://localhost:3000."

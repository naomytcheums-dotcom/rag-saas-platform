#!/usr/bin/env bash
# Partie 18 -- self-hosted uninstall. Stops and removes the real
# containers/network docker-compose.selfhosted.yml created; never
# touches .env, backups/, or Postgres's own named volume unless the
# operator explicitly opts into that with --purge-data -- an
# uninstall that silently deletes real data is the one mistake this
# script is written to never make.
set -euo pipefail

COMPOSE_FILE="docker-compose.selfhosted.yml"
PURGE_DATA=false

for arg in "$@"; do
  if [ "$arg" = "--purge-data" ]; then
    PURGE_DATA=true
  fi
done

echo "Stopping the application stack..."
docker compose -f "$COMPOSE_FILE" down

if [ "$PURGE_DATA" = true ]; then
  echo "Removing Postgres's own data volume (--purge-data was passed)..."
  docker compose -f "$COMPOSE_FILE" down -v
  echo "All real application data has been deleted."
else
  echo "Containers stopped and removed. Your database volume, .env, and backups/ are untouched."
  echo "To also permanently delete all application data, re-run: ./uninstall.sh --purge-data"
fi

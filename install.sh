#!/usr/bin/env bash
# Partie 16 (bis) -- self-hosted one-command install. Real steps only:
# no placeholder "TODO: configure X" left for the operator to guess at.
set -euo pipefail

if ! command -v docker &> /dev/null; then
  echo "Docker is required -- install it first: https://docs.docker.com/engine/install/"
  exit 1
fi
if ! docker compose version &> /dev/null; then
  echo "Docker Compose v2 is required (bundled with recent Docker Engine/Desktop)."
  exit 1
fi

if [ ! -f .env ]; then
  cp .env.example .env
  # A real, random, unique secret per install -- never the same default
  # key two self-hosted deployments would otherwise share.
  SESSION_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || openssl rand -base64 32)
  if grep -q "^SESSION_MIDDLEWARE_SECRET=" .env; then
    sed -i.bak "s#^SESSION_MIDDLEWARE_SECRET=.*#SESSION_MIDDLEWARE_SECRET=${SESSION_SECRET}#" .env && rm -f .env.bak
  fi
  echo ".env created from .env.example -- a real random SESSION_MIDDLEWARE_SECRET was generated."
  echo "Edit .env now to add: DATABASE_URL, RESEND_API_KEY (email), and a real LICENSE_KEY (see below) before continuing."
  echo "Re-run this script once .env is filled in."
  exit 0
fi

COMPOSE_FILE="docker-compose.selfhosted.yml"

echo "Starting the application stack ($COMPOSE_FILE)..."
docker compose -f "$COMPOSE_FILE" up -d --build

echo "Waiting for Postgres to become healthy..."
until docker compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U "${POSTGRES_USER:-rag_saas}" &> /dev/null; do sleep 2; done

echo "Running database migrations..."
docker compose -f "$COMPOSE_FILE" exec -T api python -m alembic upgrade head

if [ -n "${LICENSE_KEY:-}" ]; then
  echo "Validating license key..."
  curl -sf -X POST http://localhost:8000/license/validate -H "Content-Type: application/json" -d "{\"key\": \"${LICENSE_KEY}\"}" \
    && echo "" \
    || echo "License validation failed -- check LICENSE_KEY in .env and that the API container is healthy."
fi

echo ""
echo "Install complete. The API is at http://localhost:8000, the frontend at http://localhost:3000."
echo "Backup: ./scripts/backup.sh   Restore: ./scripts/restore.sh <backup-file>"

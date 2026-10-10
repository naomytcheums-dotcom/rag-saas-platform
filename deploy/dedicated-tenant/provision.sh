#!/bin/sh
# Provision (or update) a dedicated stack for one customer. Usage:  TENANT=acme API_PORT=8101 ./provision.sh
# Generates the database password and JWT secret once (kept in .env.<tenant>, mode 600, never committed), starts the stack and applies the migrations.
set -eu
: "${TENANT:?set TENANT (lowercase letters, digits and dashes)}"
case "$TENANT" in *[!a-z0-9-]*) echo "invalid TENANT" >&2; exit 1;; esac
cd "$(dirname "$0")"
ENV_FILE=".env.$TENANT"
if [ ! -f "$ENV_FILE" ]; then
  umask 077
  {
    echo "TENANT=$TENANT"
    echo "DB_PASSWORD=$(head -c 24 /dev/urandom | base64 | tr -d '/+=')"
    echo "JWT_SECRET_KEY=$(head -c 48 /dev/urandom | base64 | tr -d '/+=')"
    echo "API_PORT=${API_PORT:-8000}"
  } > "$ENV_FILE"
  echo "created $ENV_FILE (keep it secret)"
fi
docker compose --env-file "$ENV_FILE" -f docker-compose.tenant.yml up -d --build
docker compose --env-file "$ENV_FILE" -f docker-compose.tenant.yml exec -T api alembic upgrade head
echo "tenant $TENANT is up on port $(grep '^API_PORT=' "$ENV_FILE" | cut -d= -f2)"

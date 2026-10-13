#!/bin/sh
# Provision (or update) a dedicated stack for one customer. Usage:  TENANT=acme API_PORT=8101 ./provision.sh
# Generates every secret once (kept in .env.<tenant>, mode 600, never committed), builds the image, starts the stack and applies the migrations.
# Optional: SUPPORT_EMAIL, FRONTEND_URL, COOKIE_SECURE (false only for a plain-http local trial), BIND_ADDRESS (default 127.0.0.1; 0.0.0.0 behind your own
# TLS proxy), IMAGE (a pre-built image: skips the build). The compose project name is rag-saas-<tenant>.
set -eu
: "${TENANT:?set TENANT (lowercase letters, digits and dashes)}"
case "$TENANT" in *[!a-z0-9-]*) echo "invalid TENANT" >&2; exit 1;; esac
cd "$(dirname "$0")"
ENV_FILE=".env.$TENANT"
secret() { head -c 48 /dev/urandom | base64 | tr -d '\n/+='; }
key32() { head -c 32 /dev/urandom | base64 | tr '+/' '-_' | tr -d '\n'; }   # urlsafe base64 of 32 random bytes: Fernet key and AES-256 key format
if [ ! -f "$ENV_FILE" ]; then
  umask 077
  {
    echo "TENANT=$TENANT"
    echo "DB_PASSWORD=$(secret)"
    echo "JWT_SECRET_KEY=$(secret)"
    echo "SESSION_MIDDLEWARE_SECRET=$(secret)"
    echo "AUDIT_LOG_HMAC_SECRET_KEY=$(secret)"
    echo "ENCRYPTION_MASTER_KEY=$(key32)"
    echo "SECRET_ENCRYPTION_KEY=$(key32)"
    echo "SUPPORT_EMAIL=${SUPPORT_EMAIL:-support@$TENANT.invalid}"
    echo "API_PORT=${API_PORT:-8000}"
    [ -z "${FRONTEND_URL:-}" ] || echo "FRONTEND_URL=$FRONTEND_URL"
    [ -z "${COOKIE_SECURE:-}" ] || echo "COOKIE_SECURE=$COOKIE_SECURE"
    [ -z "${BIND_ADDRESS:-}" ] || echo "BIND_ADDRESS=$BIND_ADDRESS"
    [ -z "${IMAGE:-}" ] || echo "IMAGE=$IMAGE"
  } > "$ENV_FILE"
  echo "created $ENV_FILE (keep it secret: it holds the encryption keys; losing ENCRYPTION_MASTER_KEY makes the stored secrets unreadable)"
fi
if [ -n "${IMAGE:-}" ]; then
  docker compose --env-file "$ENV_FILE" -f docker-compose.tenant.yml up -d --no-build --wait
else
  docker compose --env-file "$ENV_FILE" -f docker-compose.tenant.yml up -d --build --wait
fi
docker compose --env-file "$ENV_FILE" -f docker-compose.tenant.yml exec -T api python -m alembic upgrade head
echo "tenant $TENANT is up on port $(grep '^API_PORT=' "$ENV_FILE" | cut -d= -f2)"

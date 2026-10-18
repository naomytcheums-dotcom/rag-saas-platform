#!/bin/sh
# Provision (or update) a dedicated stack for one customer. Usage:  TENANT=acme API_PORT=8101 ./provision.sh
# Generates every secret once (kept in .env.<tenant>, mode 600, never committed), starts the stack, creates the three storage buckets and applies the migrations.
# Optional (written to .env.<tenant> on first run, edit it afterwards):
#   SUPPORT_EMAIL, FRONTEND_URL, COOKIE_SECURE (false only for a plain-http trial), BIND_ADDRESS (default 127.0.0.1; 0.0.0.0 behind your own TLS proxy),
#   IMAGE (a pre-built image: skips the build), WEB_CONCURRENCY (gunicorn workers, default 4), MODELS_DIR (a directory holding the Hugging Face cache for an offline start), HF_HUB_OFFLINE (default 0; the air-gapped overlay forces 1),
#   AIRGAPPED=1 (adds docker-compose.airgapped.yml: no route to the internet), COMPOSE_PROFILES=llm (starts Ollama on the private network).
# The compose project is rag-saas-<tenant>: its containers, network and volumes are not shared with any other tenant.
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
    echo "S3_ACCESS_KEY_ID=minio$(secret | head -c 12)"
    echo "S3_SECRET_ACCESS_KEY=$(secret)"
    echo "SUPPORT_EMAIL=${SUPPORT_EMAIL:-support@$TENANT.invalid}"
    echo "API_PORT=${API_PORT:-8000}"
    for name in FRONTEND_URL COOKIE_SECURE BIND_ADDRESS IMAGE MODELS_DIR HF_HUB_OFFLINE WEB_CONCURRENCY AIRGAPPED COMPOSE_PROFILES MINIO_IMAGE EDGE_IMAGE; do
      eval "value=\${$name:-}"
      [ -z "$value" ] || echo "$name=$value"
    done
  } > "$ENV_FILE"
  echo "created $ENV_FILE (keep it secret: it holds the encryption keys; losing ENCRYPTION_MASTER_KEY makes the stored secrets unreadable)"
fi
FILES="-f docker-compose.tenant.yml"
if grep -q '^AIRGAPPED=1' "$ENV_FILE"; then FILES="$FILES -f docker-compose.airgapped.yml"; fi
COMPOSE="docker compose --env-file $ENV_FILE $FILES"
if grep -q '^IMAGE=' "$ENV_FILE"; then BUILD="--no-build"; else BUILD="--build"; fi
# The API refuses to start on an empty database (it loads the RBAC policy table at boot), so the schema is created BEFORE the API is started:
# found 2026-10-16 by running this script on a fresh tenant (the API container exited with "relation casbin_rule does not exist" and `up --wait` failed).
$COMPOSE up -d $BUILD --wait db redis minio
$COMPOSE run --rm --no-deps api python -m alembic upgrade head
$COMPOSE up -d $BUILD --wait
# the three buckets the API expects (idempotent), created with the API's own S3 client and credentials
$COMPOSE exec -T api python - <<'PY'
import os
import boto3
from botocore.exceptions import ClientError
s3 = boto3.client("s3", endpoint_url=os.environ["S3_ENDPOINT_URL"], aws_access_key_id=os.environ["S3_ACCESS_KEY_ID"], aws_secret_access_key=os.environ["S3_SECRET_ACCESS_KEY"], region_name="us-east-1")
for bucket in (os.environ["S3_BUCKET_NAME"], os.environ["S3_DOCUMENTS_BUCKET_NAME"], os.environ["S3_VOICE_BUCKET_NAME"]):
    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError:
        s3.create_bucket(Bucket=bucket)
        print("created bucket", bucket)
PY
$COMPOSE exec -T api python -m alembic upgrade head   # idempotent: already at head (kept for an update of an existing tenant)
echo "tenant $TENANT is up on port $(grep '^API_PORT=' "$ENV_FILE" | cut -d= -f2)"

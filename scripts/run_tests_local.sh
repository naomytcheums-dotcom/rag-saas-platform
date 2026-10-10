#!/bin/sh
# Run the backend tests against a DISPOSABLE local stack, never against the real services in .env.
#
#   scripts/run_tests_local.sh tests/test_auth_api.py -q
#
# Needs a local PostgreSQL with pgvector and a local Redis, for example:
#   docker run -d --name rag-test-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=rag_saas_test -p 15432:5432 pgvector/pgvector:pg16
#   docker run -d --name rag-test-redis -p 16379:6379 redis:7-alpine
#   DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:15432/rag_saas_test python -m alembic upgrade head
# Override the ports / URLs with TEST_DATABASE_URL and TEST_REDIS_URL. tests/conftest.py refuses to start if anything still points to a remote host.
set -eu
export DATABASE_URL="${TEST_DATABASE_URL:-postgresql+asyncpg://postgres:postgres@localhost:15432/rag_saas_test}"
export DATABASE_URL_TRANSACTION=""
REDIS="${TEST_REDIS_URL:-redis://localhost:16379}"
export CELERY_BROKER_URL="$REDIS/0" CELERY_RESULT_BACKEND="$REDIS/1" RATE_LIMIT_REDIS_URL="$REDIS/2" CACHE_REDIS_URL="" REDIS_URL=""
export S3_ENDPOINT_URL="http://localhost:9000" S3_ACCESS_KEY_ID="minioadmin" S3_SECRET_ACCESS_KEY="minioadmin"
export RESEND_API_KEY="re_ci_placeholder_never_a_real_key" STRIPE_SECRET_KEY="" PAYSTACK_SECRET_KEY=""
exec python -m pytest -p no:cacheprovider "$@"

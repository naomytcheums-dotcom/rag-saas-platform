# Local disposable E2E environment (no production service). Sourced by the E2E launchers.
PGPW=$(docker inspect rag-test-pg --format "{{range .Config.Env}}{{println .}}{{end}}" | grep "^POSTGRES_PASSWORD=" | cut -d= -f2-)
export DATABASE_URL="postgresql+asyncpg://rag_test:${PGPW}@127.0.0.1:25432/rag_test_infra"
export DATABASE_URL_TRANSACTION=""
R=redis://127.0.0.1:26390
export CELERY_BROKER_URL="$R/13" CELERY_RESULT_BACKEND="$R/13" RATE_LIMIT_REDIS_URL="$R/13" CACHE_REDIS_URL="" REDIS_URL="$R/13"
export S3_ENDPOINT_URL="http://localhost:9000" S3_ACCESS_KEY_ID="minioadmin" S3_SECRET_ACCESS_KEY="minioadmin"
export RAG_ENV_FILE=".no-env"
export JWT_SECRET_KEY="local-e2e-jwt-0123456789abcdef0123456789abcd" SESSION_MIDDLEWARE_SECRET="local-e2e-session-0123456789abcdef012345678" AUDIT_LOG_HMAC_SECRET_KEY="local-e2e-audit-0123456789abcdef0123456789ab" SUPPORT_EMAIL="support@example.test"
export ENCRYPTION_MASTER_KEY="$(python -c 'from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())' 2>/dev/null)"
export COOKIE_SECURE=false FRONTEND_URL="http://localhost:3000" RATE_LIMIT_ENABLED=false
export RESEND_API_KEY="re_local_placeholder" STRIPE_SECRET_KEY="" PAYSTACK_SECRET_KEY=""
export LOKI_HOST="" TEMPO_HOST="" LANGFUSE_HOST="" SENTRY_DSN="" SECURITY_ALERT_WEBHOOK_URL="" OTEL_EXPORTER_OTLP_ENDPOINT=""
export ANTHROPIC_API_KEY="" OPENAI_API_KEY="" GEMINI_API_KEY="" MISTRAL_API_KEY="" OPENAI_COMPATIBLE_API_KEY="" WATSONX_API_KEY="" VOYAGE_API_KEY="" COHERE_API_KEY="" TAVILY_API_KEY=""
export LLM_DEFAULT_PROVIDER=ollama LLM_DEFAULT_MODEL="qwen2.5:7b" OLLAMA_BASE_URL="http://127.0.0.1:11434" OLLAMA_MODEL="ollama/qwen2.5:7b"
export LLM_TIMEOUT=600 AGENT_TIMEOUT=600 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export PYTHONPATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export S3_DOCUMENTS_BUCKET_NAME=documents S3_AVATARS_BUCKET_NAME=avatars S3_VOICE_BUCKET_NAME=voice S3_REGION=us-east-1
export SECRET_ENCRYPTION_KEY="$(python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())")"

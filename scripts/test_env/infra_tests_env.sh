# Environment of the isolated test suite for this worktree (copy of the exports of scripts/run_tests_local.sh) with its own database and Redis DB 13.
# Source it, then run pytest / scripts/coverage_batches.py.
export DATABASE_URL="${TEST_DATABASE_URL:?set TEST_DATABASE_URL}"
export DATABASE_URL_TRANSACTION=""
REDIS="${TEST_REDIS_URL:-redis://localhost:16379}"
export CELERY_BROKER_URL="$REDIS/13" CELERY_RESULT_BACKEND="$REDIS/13" RATE_LIMIT_REDIS_URL="$REDIS/13" CACHE_REDIS_URL="" REDIS_URL=""
export S3_ENDPOINT_URL="http://localhost:9000" S3_ACCESS_KEY_ID="minioadmin" S3_SECRET_ACCESS_KEY="minioadmin"
export RESEND_API_KEY="re_ci_placeholder_never_a_real_key" STRIPE_SECRET_KEY="" PAYSTACK_SECRET_KEY=""
# Hosted observability services configured in .env (Grafana Cloud Loki / Tempo, Langfuse, Sentry, alert webhook): a test that switches tracing or
# logging on must never reach them. Found 2026-10-11: a tracing test exported a span to the production Tempo through these variables.
export LOKI_HOST="" LOKI_USERNAME="" LOKI_PASSWORD="" TEMPO_HOST="" TEMPO_USERNAME="" TEMPO_PASSWORD=""
# Never spend real money in tests: paid LLM / embedding / search / voice providers are blanked (opt-in tests set their own local provider).
export ANTHROPIC_API_KEY="" OPENAI_API_KEY="" GEMINI_API_KEY="" MISTRAL_API_KEY="" OPENAI_COMPATIBLE_API_KEY="" WATSONX_API_KEY="" OPENAI_EMBEDDING_API_KEY="" VOYAGE_API_KEY="" COHERE_API_KEY="" TAVILY_API_KEY="" DEEPGRAM_API_KEY="" GOOGLE_CLOUD_TTS_API_KEY="" ELEVENLABS_API_KEY="" TWILIO_AUTH_TOKEN=""
export LANGFUSE_HOST="" LANGFUSE_PUBLIC_KEY="" LANGFUSE_SECRET_KEY="" SENTRY_DSN="" SECURITY_ALERT_WEBHOOK_URL="" OTEL_EXPORTER_OTLP_ENDPOINT=""
export OTEL_EXPORTER_OTLP_ENDPOINT="" SENTRY_DSN=""
# What the project's .env provides on the main checkout and CI provides explicitly (.github/workflows/ci.yml): throw-away secrets, nothing real.
export JWT_SECRET_KEY="ci-only-jwt-secret-key-never-used-outside-ci-32c" SESSION_MIDDLEWARE_SECRET="ci-only-session-secret-never-used-outside-ci-32c"
export AUDIT_LOG_HMAC_SECRET_KEY="ci-only-audit-log-hmac-key-never-used-outside-ci-32c" SUPPORT_EMAIL="support@ci-test.invalid" EMAIL_FROM_ADDRESS="onboarding@resend.dev"
export SECRET_ENCRYPTION_KEY="t9aZv8_TY9hGq8Q0yZMkBjYAah-UwN1M6cDVkimg9AY=" ENCRYPTION_MASTER_KEY="gBZ-pfccwD20XSBiesnRCAo9e7_y7E0LOAAvsXGJXyg="
export S3_BUCKET_NAME=avatars S3_REGION=us-east-1 S3_PUBLIC_BASE_URL="http://localhost:9000/public/avatars" S3_DOCUMENTS_BUCKET_NAME=documents S3_VOICE_BUCKET_NAME=voice
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export COOKIE_SECURE=False GOOGLE_OAUTH_CLIENT_ID=ci-only-google-client-id-never-real GOOGLE_OAUTH_CLIENT_SECRET=ci-only-google-client-secret-never-real
export GITHUB_OAUTH_CLIENT_ID=ci-only-github-client-id-never-real GITHUB_OAUTH_CLIENT_SECRET=ci-only-github-client-secret-never-real

"""Runtime guard for the local PREVIEW mode (RAG_RUN_MODE=preview).

Why it exists: a local preview server once started with the real `.env` (DATABASE_URL_TRANSACTION pointing at the hosted Supabase
pooler) and created test accounts and organizations in the real database. In preview mode nothing may reach a real service:

* every data store (database, transaction pooler, Redis, Celery broker/backend, S3) must be local or an in-memory scheme, and the
  database name must carry a throwaway marker;
* every credential of an external service (payments, e-mail, telephony, chat platforms, LLM providers, Sentry, ...) must be empty;
* anything that cannot be identified (unparsable URL, empty required URL) is refused.

Pure functions, no I/O. A refusal names the setting and the rule, NEVER the value (no secret or connection string in any message).
The production behaviour is unchanged: the guard only runs when RAG_RUN_MODE=preview.
"""

import re
from collections.abc import Mapping
from urllib.parse import urlparse

RUN_MODE_VARIABLE = "RAG_RUN_MODE"
PREVIEW_MODE = "preview"

LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
IN_MEMORY_SCHEMES = frozenset({"memory", "cache+memory", "filesystem"})
DATABASE_MARKER = re.compile(r"(preview|disposable|roundtrip|scratch|throwaway|test)", re.IGNORECASE)

REQUIRED_DATABASE = "DATABASE_URL"
OPTIONAL_DATABASE = ("DATABASE_URL_TRANSACTION", "STAGING_DATABASE_URL", "MAIN_DATABASE_URL")
LOCAL_ENDPOINTS = ("RATE_LIMIT_REDIS_URL", "CACHE_REDIS_URL", "REDIS_URL", "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND", "S3_ENDPOINT_URL")

# Credentials of a service that is NOT needed to preview the interface: must be empty. Internal application secrets
# (signing keys, encryption keys) are not external credentials and are therefore not listed here.
INTERNAL_SECRETS = frozenset({
    "JWT_SECRET_KEY", "JWT_PREVIOUS_SECRET_KEYS", "SESSION_MIDDLEWARE_SECRET", "AUDIT_LOG_HMAC_SECRET_KEY", "ENCRYPTION_MASTER_KEY",
    "SECRET_ENCRYPTION_KEY", "METRICS_AUTH_TOKEN", "DISCORD_GATEWAY_SHARED_SECRET",
})
EXTERNAL_CREDENTIAL = re.compile(r"(_API_KEY|_SECRET|_SECRET_KEY|_AUTH_TOKEN|_BOT_TOKEN|_SIGNING_SECRET|_DSN|_WEBHOOK_URL|_CLIENT_SECRET|_ACCOUNT_SID|_KEY_SID)$")
EXTERNAL_PREFIXES = ("STRIPE_", "PAYSTACK_", "RESEND_", "TWILIO_", "ANTHROPIC_", "OPENAI_", "MISTRAL_", "GEMINI_", "GOOGLE_", "GITHUB_", "SLACK_", "DISCORD_", "AIRBYTE_", "SENTRY_", "NOTION_", "VOYAGE_", "COHERE_", "HUGGINGFACE_")


def is_preview(env: Mapping[str, object]) -> bool:
    return str(env.get(RUN_MODE_VARIABLE, "") or "").strip().lower() == PREVIEW_MODE


def _host_and_scheme(url: str) -> tuple[str | None, str]:
    try:
        parsed = urlparse(url.strip())
        return (parsed.hostname or "").lower() or None, (parsed.scheme or "").lower()
    except ValueError:
        return None, ""


def _database_name(url: str) -> str:
    try:
        return urlparse(url.strip()).path.lstrip("/")
    except ValueError:
        return ""


def _is_credential_name(name: str) -> bool:
    if name in INTERNAL_SECRETS or name in LOCAL_ENDPOINTS or name == REQUIRED_DATABASE or name in OPTIONAL_DATABASE:
        return False
    if name.startswith(("S3_",)) or name.endswith(("_PUBLISHABLE_KEY", "_PUBLIC_KEY")):
        return False
    return bool(EXTERNAL_CREDENTIAL.search(name)) and name.startswith(EXTERNAL_PREFIXES)


def preview_refusals(env: Mapping[str, object]) -> list[str]:
    """Every reason the preview must not start (empty list = allowed). `env` maps a setting name to its value (None/'' = unset)."""
    refusals: list[str] = []

    def value(name: str) -> str:
        raw = env.get(name)
        return "" if raw is None else str(raw).strip()

    database = value(REQUIRED_DATABASE)
    if not database:
        refusals.append(f"{REQUIRED_DATABASE} is not set: the preview database cannot be identified")
    else:
        host, _scheme = _host_and_scheme(database)
        if host not in LOCAL_HOSTS:
            refusals.append(f"{REQUIRED_DATABASE} is not a local database (host must be 127.0.0.1, localhost or ::1)")
        elif not DATABASE_MARKER.search(_database_name(database)):
            refusals.append(f"{REQUIRED_DATABASE}: the database name must contain preview, disposable, roundtrip, scratch, throwaway or test")
    for name in OPTIONAL_DATABASE:
        other = value(name)
        if not other:
            continue
        host, _scheme = _host_and_scheme(other)
        if host not in LOCAL_HOSTS or not DATABASE_MARKER.search(_database_name(other)):
            refusals.append(f"{name} must be unset or a local throwaway database (it may be a hosted pooler)")
    for name in LOCAL_ENDPOINTS:
        endpoint = value(name)
        if not endpoint:
            continue
        host, scheme = _host_and_scheme(endpoint)
        if scheme in IN_MEMORY_SCHEMES:
            continue
        if host not in LOCAL_HOSTS:
            refusals.append(f"{name} must be unset, an in-memory scheme or a local address")
    for name in sorted(env):
        if _is_credential_name(name) and value(name):
            refusals.append(f"{name} holds an external-service credential: it must be empty in preview mode")
    return refusals


class PreviewRefused(ValueError):
    """Raised at start-up when RAG_RUN_MODE=preview and the configuration could reach a real service."""


def assert_preview_is_isolated(env: Mapping[str, object]) -> None:
    problems = preview_refusals(env)
    if problems:
        raise PreviewRefused("preview mode refused to start: " + "; ".join(problems))

"""
Phase 5, Étape 7 -- real Sentry error tracking, disabled by default
(`SENTRY_DSN` empty) since this environment has no real Sentry project
DSN configured -- initializing the SDK with no DSN is itself a
documented Sentry no-op, but this module makes that explicit and
testable rather than silently relying on the SDK's own default.

Same "real code, off unless configured" pattern as
`api/security/tracing.py` (OpenTelemetry) right above it in
`api/main.py`'s own lifespan -- an operator who sets `SENTRY_DSN` (and
optionally `SENTRY_ENVIRONMENT`/`SENTRY_TRACES_SAMPLE_RATE`) in their
own `.env` gets real, working error capture with zero code changes;
one who doesn't gets a real, inert no-op, not a placeholder.
"""

import logging

from api.config import settings

logger = logging.getLogger(__name__)

_initialized = False


def setup_error_tracking() -> None:
    global _initialized
    if not settings.SENTRY_DSN or _initialized:
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.SENTRY_ENVIRONMENT,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            integrations=[StarletteIntegration(), FastApiIntegration(), CeleryIntegration()],
            # Real secret hygiene, same reasoning as `agent_orchestrator.py`'s own
            # `_redact_secrets`: request bodies/headers can carry API keys,
            # passwords, or tokens (login/API-key endpoints) -- never sent as-is.
            send_default_pii=False,
        )
        _initialized = True
    except Exception:  # noqa: BLE001 -- error tracking failing to initialize must never crash the app it's meant to observe
        logger.exception("failed to initialize Sentry error tracking despite SENTRY_DSN being set")


def error_tracking_status() -> dict:
    """Real, honest status for `GET /monitoring/*`-style introspection --
    same shape/purpose as `api/security/tracing.py`'s own `tracing_status`."""
    return {"enabled": bool(settings.SENTRY_DSN), "initialized": _initialized, "environment": settings.SENTRY_ENVIRONMENT if settings.SENTRY_DSN else None}

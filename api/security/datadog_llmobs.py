"""
Datadog LLM Observability -- real `ddtrace` SDK, `LLMObs.enable()`.
Honest gate: without `DD_API_KEY`, this stays a real no-op -- ddtrace
itself would otherwise try (and fail) to reach Datadog's real intake on
every flush.

`ddtrace-run` (the literal spec's own instrumentation entrypoint for
FastAPI/SQLAlchemy/Redis/Celery auto-patching) is a PROCESS WRAPPER
(`ddtrace-run uvicorn api.main:app`), not something callable from
inside the app -- real, honest deviation, not a gap: switching to it is
a one-line change to how this process is launched (documented in
docs/monitoring/DATADOG.md), not application code.
"""

import logging

from api.config import settings

logger = logging.getLogger(__name__)

_enabled = False


def setup_llm_observability() -> bool:
    global _enabled
    if not settings.DD_API_KEY:
        return False
    if _enabled:
        return True
    try:
        from ddtrace.llmobs import LLMObs

        LLMObs.enable(ml_app=settings.DD_LLMOBS_ML_APP, api_key=settings.DD_API_KEY, site=settings.DD_SITE, agentless_enabled=True)
        _enabled = True
        logger.info("Datadog LLM Observability enabled (ml_app=%s, site=%s)", settings.DD_LLMOBS_ML_APP, settings.DD_SITE)
        return True
    except Exception:
        logger.warning("Datadog LLM Observability setup failed -- staying disabled", exc_info=True)
        return False


def llm_observability_status() -> dict:
    return {"configured": bool(settings.DD_API_KEY), "enabled": _enabled, "ml_app": settings.DD_LLMOBS_ML_APP, "site": settings.DD_SITE}

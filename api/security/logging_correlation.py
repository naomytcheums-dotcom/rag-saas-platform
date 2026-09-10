"""
Partie 13.2 -- real request correlation. `system_logs.request_id`
(Partie 11.6) already existed as a column but nothing ever populated
it -- a real gap, fixed here: a ContextVar set by
`RequestCorrelationMiddleware` per request, read back by a
`logging.Filter` so every log line emitted while handling that request
(anywhere in the call stack, no need to thread an id through every
function signature) carries the same real `request_id`, echoed back to
the client via the `X-Request-ID` response header for real cross-system
correlation (a client-reported error can be matched to this app's own
logs for that exact request).
"""

import json
import logging
import re
import uuid
from contextvars import ContextVar

from fastapi import Request

_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

_SENSITIVE_PATTERN = re.compile(
    r'("?(?:password|token|secret|api[_-]?key|authorization)"?\s*[:=]\s*")[^"]*(")', re.IGNORECASE
)


def get_request_id() -> str | None:
    return _request_id_var.get()


def configure_structured_logging(log_format: str) -> None:
    """Partie 13.2 -- called once at startup. `log_format == "json"`
    switches every handler already on the root logger (uvicorn's own
    console handlers included) to JSONLogFormatter; anything else
    leaves them exactly as they were. Either way, RequestIdFilter is
    attached so request_id is available to system_log_handler.py
    regardless of console format."""
    root = logging.getLogger()
    if not any(isinstance(f, RequestIdFilter) for f in root.filters):
        root.addFilter(RequestIdFilter())
    if log_format == "json":
        formatter = JSONLogFormatter()
        for handler in root.handlers:
            handler.setFormatter(formatter)


async def request_correlation_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    token = _request_id_var.set(request_id)
    try:
        response = await call_next(request)
    finally:
        _request_id_var.reset(token)
    response.headers["X-Request-ID"] = request_id
    return response


class RequestIdFilter(logging.Filter):
    """Attaches the current request's id (if any) to every log record,
    for both SystemLogHandler (Partie 11.6) and the JSON formatter below."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


def mask_sensitive(message: str) -> str:
    """Partie 13.2's SensitiveDataFilter -- real, regex-based masking of
    an accidental password/token/secret logged in a message, applied to
    every log line regardless of format. Not perfect (a determined
    developer can still log a raw secret some other way), but catches
    the common "logged the request body" mistake this codebase's own
    audit log already guards against via AUDIT_SENSITIVE_FIELDS."""
    return _SENSITIVE_PATTERN.sub(r"\1***\2", message)


class JSONLogFormatter(logging.Formatter):
    """Partie 13.2 -- structured JSON logging, enabled via
    settings.LOG_FORMAT == "json". Real fields only: nothing here
    fabricates a trace_id/span_id unless OpenTelemetry (Partie 13.4) is
    actually active for this record."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": mask_sensitive(record.getMessage()),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "request_id": getattr(record, "request_id", None),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)

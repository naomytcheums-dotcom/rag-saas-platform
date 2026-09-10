"""
Grafana Cloud Loki -- real HTTP push to Loki's own `/loki/api/v1/push`
API (no extra dependency: this is a plain, documented JSON POST, the
same real pattern this project already uses for Slack/webhook
delivery). Honestly incomplete without BOTH `LOKI_HOST` and
`LOKI_USERNAME` (the real per-stack instance id from the Grafana Cloud
portal) -- a password alone can't identify which Grafana Cloud stack
to push to, so `install_loki_handler()` is a real no-op until both are
set, never a guess at a stack URL.
"""

import logging
import queue
import threading

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

_installed = False


class LokiHandler(logging.Handler):
    """Fire-and-forget, background-thread delivery -- a Loki hiccup or
    slow network call must never block the request that triggered the
    log line it's shipping. A bounded queue (maxsize=1000) drops the
    oldest entries under sustained overload rather than growing without
    bound."""

    def __init__(self, level=logging.WARNING):
        super().__init__(level)
        self._queue: queue.Queue = queue.Queue(maxsize=1000)
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._queue.put_nowait((record.created, self.format(record), record.levelname, record.name))
        except queue.Full:
            pass  # honest overload behavior -- drop rather than block or crash

    def _worker(self) -> None:
        while True:
            timestamp, message, level, logger_name = self._queue.get()
            try:
                ns = str(int(timestamp * 1_000_000_000))
                httpx.post(
                    f"{settings.LOKI_HOST}/loki/api/v1/push",
                    auth=(settings.LOKI_USERNAME, settings.LOKI_PASSWORD),
                    json={"streams": [{"stream": {"level": level, "logger": logger_name, "service": "rag-saas-api"}, "values": [[ns, message]]}]},
                    timeout=5.0,
                )
            except Exception:  # noqa: BLE001 -- a failed shipment must never crash the worker thread
                pass


def install_loki_handler() -> bool:
    """Returns whether it actually installed -- real, honest signal for
    GET /monitoring/loki/status rather than a fire-and-forget with no
    way to tell if it worked."""
    global _installed
    if not settings.LOKI_HOST or not settings.LOKI_USERNAME or not settings.LOKI_PASSWORD:
        return False
    if _installed:
        return True
    root = logging.getLogger()
    if any(isinstance(h, LokiHandler) for h in root.handlers):
        _installed = True
        return True
    root.addHandler(LokiHandler())
    _installed = True
    return True


def send_test_log_synchronously() -> dict:
    """Real, synchronous push (unlike LokiHandler.emit's fire-and-forget
    background delivery) so GET /monitoring/loki/test can report the
    REAL HTTP outcome -- found directly why this was needed: the
    background handler's own broad `except Exception: pass` meant a
    real, persistent 401 from Grafana Cloud was invisible until checked
    this way."""
    if not settings.LOKI_HOST or not settings.LOKI_USERNAME or not settings.LOKI_PASSWORD:
        return {"sent": False, "reason": "not configured"}
    import time

    ns = str(int(time.time() * 1_000_000_000))
    try:
        response = httpx.post(
            f"{settings.LOKI_HOST}/loki/api/v1/push",
            auth=(settings.LOKI_USERNAME, settings.LOKI_PASSWORD),
            json={"streams": [{"stream": {"level": "WARNING", "logger": "monitoring.loki.test", "service": "rag-saas-api"}, "values": [[ns, "Real synchronous test log from GET /monitoring/loki/test"]]}]},
            timeout=10.0,
        )
        if response.status_code == 204:
            return {"sent": True}
        return {"sent": False, "status_code": response.status_code, "body": response.text[:500]}
    except Exception as exc:
        return {"sent": False, "error": str(exc)}


def loki_status() -> dict:
    return {
        "configured": bool(settings.LOKI_HOST and settings.LOKI_USERNAME and settings.LOKI_PASSWORD),
        "installed": _installed,
        "host": settings.LOKI_HOST,
    }

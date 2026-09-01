"""
Audit finding 22 -- request-duration instrumentation, exposed at GET
/metrics in Prometheus's own text exposition format.

Uses the real `prometheus_client` library (not hand-rolled, unlike
api/security/rate_limit.py's sliding window or password_similarity.py's
Levenshtein distance) specifically for its multiprocess mode: correctly
aggregating a histogram across several worker PROCESSES -- one mmap'd
file per worker, merged at scrape time, with dead workers' files cleaned
up as they exit -- is real, easy-to-get-subtly-wrong complexity a
battle-tested library exists to solve, not logic worth reinventing.

Multiprocess mode activates itself the moment the PROMETHEUS_MULTIPROC_DIR
environment variable is set (prometheus_client reads it directly, not
through api/config.py's Settings) -- see gunicorn.conf.py for how a real
multi-worker production deployment wires this up (directory creation/
cleanup on startup, marking a worker's data dead the moment it exits).
Unset (the default -- local dev's `uvicorn api.main:app --reload`, or a
single-worker deployment), everything here still works exactly as
before: one process, one in-memory registry, nothing multiprocess-aware
to configure.
"""

import os
import time

from fastapi import Request, Response
from prometheus_client import CollectorRegistry, Histogram, generate_latest, multiprocess

# Seconds -- prometheus_client's own default histogram buckets, so a
# dashboard built against those defaults still makes sense here.
_DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0)

REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "Time spent handling an HTTP request, in seconds.",
    labelnames=("method", "path"),
    buckets=_DEFAULT_BUCKETS,
)


async def track_request_duration_middleware(request: Request, call_next) -> Response:
    """
    The route's own PATH TEMPLATE (e.g. "/sessions/{session_id}"), not
    the literal request path -- request.url.path for
    GET /sessions/<uuid> would otherwise create a brand new metrics
    series per session id ever requested, growing without bound for as
    long as the process (or, in multiprocess mode, the shared metrics
    directory) lives. request.scope["route"] is only populated once
    FastAPI has actually matched a route, which happens INSIDE
    call_next() -- read after awaiting it, not before.

    A request matching no route at all (a 404, or anything before
    routing) is bucketed under the single fixed label "unmatched" rather
    than its raw literal path, for the same unbounded-cardinality reason
    -- an attacker probing thousands of random nonexistent paths must
    not be able to grow this metric's series count by one per guess.

    Timed manually rather than with Histogram.labels(...).time()'s
    context-manager sugar: that records its observation under whatever
    labels were passed BEFORE the timed block runs, but the real route
    (and therefore the real `path` label) isn't known until AFTER
    call_next() returns and FastAPI has actually matched one.
    """
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start

    route = request.scope.get("route")
    path = route.path if route is not None else "unmatched"
    REQUEST_DURATION_SECONDS.labels(method=request.method, path=path).observe(duration)
    return response


def render_prometheus_metrics() -> bytes:
    """
    Single-process (default): reads straight from this process's own
    in-memory registry, same as any ordinary prometheus_client app.

    Multiprocess (PROMETHEUS_MULTIPROC_DIR set): builds a throwaway
    CollectorRegistry and asks MultiProcessCollector to merge every
    worker's mmap'd metrics files into it -- this is the actual fix for
    the earlier hand-rolled version's known limitation (each worker
    reporting only its own slice of traffic).
    """
    if "PROMETHEUS_MULTIPROC_DIR" in os.environ:
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        return generate_latest(registry)
    return generate_latest()

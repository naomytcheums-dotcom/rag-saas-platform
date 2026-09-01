"""
Audit finding 22 -- request-duration instrumentation, exposed at GET
/metrics in Prometheus's own text exposition format (so a real Prometheus
server can scrape this endpoint directly with zero translation, and
`promtool check metrics` or any Prometheus client library can parse it) --
without pulling in the `prometheus_client` dependency for what's a
genuinely small amount of logic (a cumulative histogram is a dict of
counters), same "no dependency for logic this short" reasoning as
api/security/rate_limit.py and api/security/password_similarity.py.

Known, deliberate limitation: this is in-process, in-memory state. A
single uvicorn worker sees a complete picture of its own traffic; a
multi-worker deployment (multiple uvicorn/gunicorn processes) would have
each worker report only ITS OWN slice, with Prometheus scraping whichever
worker happens to answer a given request -- the real prometheus_client
library's multiprocess mode solves this with shared file-based storage,
which is a fair upgrade if this ever runs with more than one worker
process. Documented here rather than silently pretended away.
"""

import time
from collections import defaultdict

from fastapi import Request, Response

# Seconds -- matches prometheus_client's own default histogram buckets,
# so a dashboard built against those defaults still makes sense here.
_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0)


class _Metric:
    __slots__ = ("count", "sum", "bucket_counts")

    def __init__(self):
        self.count = 0
        self.sum = 0.0
        # Cumulative from the start -- bucket_counts[b] is "how many
        # observations were <= b", matching Prometheus's own histogram
        # semantics directly (each `le` line IS the cumulative count).
        self.bucket_counts: dict[float, int] = {b: 0 for b in _BUCKETS}


_metrics: dict[tuple[str, str], _Metric] = defaultdict(_Metric)


def record_request_duration(method: str, path: str, duration_seconds: float) -> None:
    metric = _metrics[(method, path)]
    metric.count += 1
    metric.sum += duration_seconds
    for bucket in _BUCKETS:
        if duration_seconds <= bucket:
            metric.bucket_counts[bucket] += 1


def render_prometheus_metrics() -> str:
    lines = [
        "# HELP http_request_duration_seconds Time spent handling an HTTP request, in seconds.",
        "# TYPE http_request_duration_seconds histogram",
    ]
    for (method, path), metric in sorted(_metrics.items()):
        labels = f'method="{method}",path="{path}"'
        for bucket in _BUCKETS:
            lines.append(f'http_request_duration_seconds_bucket{{{labels},le="{bucket}"}} {metric.bucket_counts[bucket]}')
        lines.append(f'http_request_duration_seconds_bucket{{{labels},le="+Inf"}} {metric.count}')
        lines.append(f"http_request_duration_seconds_sum{{{labels}}} {metric.sum}")
        lines.append(f"http_request_duration_seconds_count{{{labels}}} {metric.count}")
    return "\n".join(lines) + "\n"


async def track_request_duration_middleware(request: Request, call_next) -> Response:
    """
    The route's own PATH TEMPLATE (e.g. "/sessions/{session_id}"), not
    the literal request path -- request.url.path for
    GET /sessions/<uuid> would otherwise create a brand new metrics
    series per session id ever requested, growing this process's memory
    without bound for as long as it runs. request.scope["route"] is only
    populated once FastAPI has actually matched a route, which happens
    INSIDE call_next() -- read after awaiting it, not before.

    A request matching no route at all (a 404, or anything CORS'd
    preflight before routing) is bucketed under the single fixed label
    "unmatched" rather than its raw literal path, for the same
    unbounded-cardinality reason -- an attacker probing thousands of
    random nonexistent paths must not be able to grow this process's
    metrics memory by one series per guess.
    """
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start

    route = request.scope.get("route")
    path = route.path if route is not None else "unmatched"
    record_request_duration(request.method, path, duration)
    return response

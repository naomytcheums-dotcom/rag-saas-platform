"""
Production entry point for api/ when running with more than one worker
process: `PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc gunicorn -c
gunicorn.conf.py api.main:app`.

Not used by the repo's own Dockerfile -- that image runs the RAG
pipeline's Streamlit dashboard (see its own top comment), a separate
deployable from api/ entirely -- and not used by local dev, which stays
on `uvicorn api.main:app --reload` (api/main.py's own docstring, single
process, PROMETHEUS_MULTIPROC_DIR unset, nothing here relevant at all).
This exists for whichever platform/config actually deploys api/ itself
to production with multiple workers.

Plain `uvicorn --workers N` also runs multiple processes, but doesn't
expose any hook for "a worker just exited" -- Gunicorn's own docs
recommend it as the process manager for exactly this reason, and the
on_starting/child_exit pair below is the specific thing that requires it
over bare Uvicorn multi-worker mode.
"""

import glob
import os

from prometheus_client import multiprocess

bind = "0.0.0.0:8000"
workers = int(os.environ.get("WEB_CONCURRENCY", 4))
worker_class = "uvicorn.workers.UvicornWorker"


def on_starting(server):
    """
    Audit finding 22's multiprocess fix: PROMETHEUS_MULTIPROC_DIR must be
    one directory every worker process shares, and it must be EMPTY
    before any of them starts writing to it. A stale *.db file left over
    from a previous run of this same server (an earlier deploy, a
    crashed worker that never got cleaned up) would otherwise be
    included in every aggregated /metrics response forever, as if that
    long-dead worker were still reporting live traffic.
    """
    multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if not multiproc_dir:
        return
    os.makedirs(multiproc_dir, exist_ok=True)
    for stale_file in glob.glob(os.path.join(multiproc_dir, "*.db")):
        os.remove(stale_file)


def child_exit(server, worker):
    """
    Called the moment a worker process actually exits (scaled down,
    restarted, crashed) -- tells prometheus_client's multiprocess mode
    that worker is gone. Verified directly what this actually does
    (tests/test_monitoring.py) rather than assumed: it only removes a
    dead worker's GAUGE files (a "current value" metric like in-flight
    request count, which genuinely stops being current once the process
    reporting it no longer exists) -- Counter/Histogram data, like
    REQUEST_DURATION_SECONDS above, is correctly left untouched, since a
    request that worker really did serve before dying must remain part
    of the cumulative total forever. Kept here anyway even though this
    app has no Gauge metrics today: it's the correct, recommended
    Gunicorn integration regardless, and costs nothing to have wired up
    before the day a Gauge metric is actually added.

    Real bug fixed here (2026-09-17, found via a real Render deploy
    crash): unlike on_starting above, this had no guard for
    PROMETHEUS_MULTIPROC_DIR being unset -- mark_process_dead reads that
    same env var internally and does `os.path.join(None, ...)` when
    it's missing, a real TypeError that killed the whole arbiter the
    moment any worker exited (including this Dockerfile's own graceful
    restart during a deploy), not just a degraded metrics feature. Same
    "not configured -> real no-op" guard as on_starting, not assumed
    fixed by only setting the env var in the Dockerfile -- a future
    deploy target that reuses this same file without setting it must
    not crash either.
    """
    if not os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        return
    multiprocess.mark_process_dead(worker.pid)

"""
Audit finding 22's multiprocess fix -- proves /metrics actually
aggregates observations recorded by SEPARATE OS PROCESSES, not just that
the code plausibly should. This can't be done by monkeypatching
os.environ inside the current test process: prometheus_client's
Histogram only becomes multiprocess-aware if PROMETHEUS_MULTIPROC_DIR is
set BEFORE the metric object is created, and api.monitoring was already
imported single-process by the time any test in this suite runs. Real
subprocesses, each importing api.monitoring fresh with the env var
already set, are what genuinely exercises the multiprocess code path --
the same thing several real Gunicorn workers do in production.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _run(code: str, multiproc_dir: str) -> subprocess.CompletedProcess:
    # Inherits the FULL parent environment (os.environ.copy()), only
    # adding PROMETHEUS_MULTIPROC_DIR on top -- a stripped-down
    # environment risks subtle, unrelated subprocess failures (e.g.
    # SYSTEMROOT-dependent behavior on Windows), and a real Gunicorn
    # deployment only ever ADDS this one variable to an otherwise normal
    # environment too.
    env = os.environ.copy()
    env["PROMETHEUS_MULTIPROC_DIR"] = multiproc_dir
    return subprocess.run(
        [sys.executable, "-c", code], cwd=PROJECT_ROOT, capture_output=True, text=True, env=env, timeout=30,
    )


def test_metrics_aggregate_across_separate_worker_processes():
    with tempfile.TemporaryDirectory() as multiproc_dir:
        worker_code = (
            "from api.monitoring import REQUEST_DURATION_SECONDS\n"
            "REQUEST_DURATION_SECONDS.labels(method='GET', path='/health').observe(0.01)\n"
        )
        for _ in range(2):  # two separate processes, standing in for two Gunicorn workers
            result = _run(worker_code, multiproc_dir)
            assert result.returncode == 0, result.stderr

        reader_code = (
            "from api.monitoring import render_prometheus_metrics\n"
            "print(render_prometheus_metrics().decode())\n"
        )
        result = _run(reader_code, multiproc_dir)
        assert result.returncode == 0, result.stderr
        body = result.stdout

        # The aggregate count is 2 -- one observation from EACH of the
        # two separate worker processes, merged by MultiProcessCollector
        # reading both their files from the shared directory. A single-
        # process (or broken multiprocess) implementation would only
        # ever show 1 here, whichever process happened to answer the
        # scrape -- this is the exact failure mode the earlier hand-rolled,
        # in-memory-only version had.
        assert 'http_request_duration_seconds_count{method="GET",path="/health"} 2.0' in body


def test_a_dead_workers_histogram_data_is_retained_not_discarded():
    """
    A real finding from actually running this, not an assumption:
    multiprocess.mark_process_dead() (gunicorn.conf.py's child_exit
    hook) only removes a dead worker's GAUGE files (gauge_livesum/
    gauge_liveall -- "current" values that stop being current the moment
    the process reporting them is gone). It does NOT touch Counter/
    Histogram files, which is correct: a request that worker genuinely
    served before dying really did happen, and a cumulative total must
    never shrink just because the process that contributed to it later
    exited -- that's what makes it "cumulative." Proven directly here,
    since the alternative (this test originally asserted the data
    SHOULD disappear) would mean every worker restart silently erases
    real historical traffic from every dashboard built on this metric.
    """
    with tempfile.TemporaryDirectory() as multiproc_dir:
        worker_code = (
            "import os\n"
            "from api.monitoring import REQUEST_DURATION_SECONDS\n"
            "REQUEST_DURATION_SECONDS.labels(method='GET', path='/health').observe(0.01)\n"
            "print(os.getpid())\n"
        )
        result = _run(worker_code, multiproc_dir)
        assert result.returncode == 0, result.stderr
        worker_pid = result.stdout.strip()

        mark_dead_code = f"from prometheus_client import multiprocess\nmultiprocess.mark_process_dead({worker_pid})\n"
        result = _run(mark_dead_code, multiproc_dir)
        assert result.returncode == 0, result.stderr

        reader_code = (
            "from api.monitoring import render_prometheus_metrics\n"
            "print(render_prometheus_metrics().decode())\n"
        )
        body = _run(reader_code, multiproc_dir).stdout
        assert 'http_request_duration_seconds_count{method="GET",path="/health"} 1.0' in body

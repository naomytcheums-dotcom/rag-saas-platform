"""Run the REAL Celery beat on an accelerated schedule, next to a real worker, to prove that the periodic tasks are scheduled, dispatched and executed.

Windows cannot start a worker with `-B`, so beat and the worker are two processes:

    # terminal 1 (a disposable database and a Redis that nobody else uses; hosted services blanked, see scripts/run_tests_local.sh)
    python scripts/test_env/celery_beat_probe.py worker
    # terminal 2
    python scripts/test_env/celery_beat_probe.py beat            # every picked task every 8 s; stop with Ctrl+C after a minute

Then count the "succeeded" lines per task in the worker output. Run on 2026-10-11 against an empty disposable database: 17 tasks x 10 executions, 170 succeeded,
0 failed. An empty database proves scheduling, dispatch, database access and the absence of a crash, not the processing of real data (other tests cover that).

Never run it with the application's .env: several of these tasks write to the database they are given."""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from api.tasks.celery_app import celery_app  # noqa: E402

PICKED = [
    "check-modified-documents-daily", "check-scheduled-reindexes", "purge-deleted-accounts-daily", "purge-expired-conversations-retention-daily",
    "purge-expired-token-blacklist-entries-daily", "send-pending-deletion-reminders-daily", "check-pending-domain-verifications",
    "requeue-stale-pending-documents", "sync-external-sources-daily", "process-integration-webhooks-hourly", "retry-failed-integration-syncs-hourly",
    "mark-overdue-invoices-daily", "purge-old-notifications-daily", "reset-api-key-quotas-hourly", "check-usage-limits-hourly",
    "rotate-jwt-signing-key-daily-check", "check-alert-rules",
]


def main(role: str) -> None:
    if role == "worker":
        celery_app.start(argv=["worker", "-P", "solo", "-l", "INFO", "--without-gossip", "--without-mingle"])
    elif role == "beat":
        schedule = celery_app.conf.beat_schedule
        celery_app.conf.beat_schedule = {name: {**schedule[name], "schedule": 8.0} for name in PICKED if name in schedule}
        print("BEAT PICKED:", sorted(celery_app.conf.beat_schedule), flush=True)
        state = Path(tempfile.gettempdir()) / "celery-beat-probe-schedule"
        celery_app.start(argv=["beat", "-l", "INFO", "-s", str(state), "--max-interval", "4"])
    else:
        raise SystemExit("usage: celery_beat_probe.py worker|beat")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")

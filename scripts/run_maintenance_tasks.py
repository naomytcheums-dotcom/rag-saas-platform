"""Run the daily maintenance tasks once, without a Celery worker, broker or beat (spec 1.1.10).

    python scripts/run_maintenance_tasks.py              # run every task listed below
    python scripts/run_maintenance_tasks.py purge_deleted_accounts

Each task is a normal function behind a Celery decorator and is idempotent (it only touches rows that are due), so it is safe to run this
script from any scheduler: a Render cron job (deploy/render/render.api.yaml), a Kubernetes CronJob or the host's cron. A failing task does not
stop the others; the exit code is 1 when at least one failed. Needs DATABASE_URL (and the usual secrets) in the environment.
"""

from __future__ import annotations

import importlib
import logging
import sys

logger = logging.getLogger("maintenance")

# name -> (module, attribute)
TASKS: dict[str, tuple[str, str]] = {
    "purge_deleted_accounts": ("api.tasks.account_purge", "purge_deleted_accounts"),
    "send_pending_deletion_reminders": ("api.tasks.account_deletion_reminder", "send_pending_deletion_reminders"),
    "purge_expired_blacklist_entries": ("api.tasks.token_blacklist_cleanup", "purge_expired_blacklist_entries"),
    "purge_expired_conversations": ("api.tasks.retention", "purge_expired_conversations_task"),
}


def run(names: list[str], import_module=importlib.import_module) -> dict[str, str]:
    """Run the named tasks in order and return {name: "ok: <result>" | "failed: <error>"}."""
    outcome: dict[str, str] = {}
    for name in names:
        if name not in TASKS:
            outcome[name] = "failed: unknown task"
            continue
        module, attribute = TASKS[name]
        try:
            result = getattr(import_module(module), attribute)()
            outcome[name] = f"ok: {result}"
        except Exception as error:  # one broken task must not block the others
            logger.exception("maintenance task %s failed", name)
            outcome[name] = f"failed: {type(error).__name__}"
    return outcome


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    names = list(argv if argv is not None else sys.argv[1:]) or list(TASKS)
    outcome = run(names)
    for name, state in outcome.items():
        print(f"{name}: {state}")
    return 1 if any(state.startswith("failed") for state in outcome.values()) else 0


if __name__ == "__main__":
    sys.exit(main())

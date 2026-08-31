"""
Celery app + beat schedule. Run a worker with:
    celery -A api.tasks.celery_app worker --loglevel=info
and beat (the periodic-task scheduler, needed for the daily purge sweep)
with:
    celery -A api.tasks.celery_app beat --loglevel=info
Both need CELERY_BROKER_URL/CELERY_RESULT_BACKEND reachable (Redis by
default -- see api/config.py); a Postgres-backed broker also works if
Redis isn't part of the deployment, just change the URL scheme.
"""

from celery import Celery
from celery.schedules import crontab

from api.config import settings

celery_app = Celery(
    "rag_saas_platform",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    # Explicit, not autodiscover_tasks(): autodiscover_tasks(["api.tasks"])
    # looks for a submodule literally named api/tasks/tasks.py, which
    # doesn't exist here (the task lives in account_purge.py) -- it would
    # silently register zero tasks. `include` is resolved lazily, after
    # `celery_app` below is fully constructed, so account_purge.py's own
    # `from api.tasks.celery_app import celery_app` doesn't circular-import.
    include=["api.tasks.account_purge"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

celery_app.conf.beat_schedule = {
    "purge-deleted-accounts-daily": {
        "task": "api.tasks.account_purge.purge_deleted_accounts",
        "schedule": crontab(hour=3, minute=0),  # low-traffic hour, UTC
    }
}

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

from datetime import timedelta

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
    include=[
        "api.tasks.account_purge", "api.tasks.token_blacklist_cleanup", "api.tasks.account_deletion_reminder",
        "api.tasks.jwt_key_rotation", "api.tasks.ssl_certificate_renewal", "api.tasks.domain_verification",
        "api.tasks.document_processing", "api.tasks.document_modification_check", "api.tasks.external_source_sync",
        "api.tasks.reindex_schedule", "api.tasks.batch_jobs",
    ],
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
    },
    "purge-expired-token-blacklist-entries-daily": {
        "task": "api.tasks.token_blacklist_cleanup.purge_expired_blacklist_entries",
        "schedule": crontab(hour=3, minute=15),  # same low-traffic window, offset so the two don't contend
    },
    "send-pending-deletion-reminders-daily": {
        "task": "api.tasks.account_deletion_reminder.send_pending_deletion_reminders",
        "schedule": crontab(hour=3, minute=30),  # same low-traffic window, offset again
    },
    # Audit finding 28 -- checked daily, same low-traffic window, but
    # only ever ACTS once every JWT_AUTO_ROTATION_INTERVAL_DAYS: the task
    # itself is the one that decides whether the current key is actually
    # due (see api/tasks/jwt_key_rotation.py's own docstring), same
    # "safe to run on any schedule" idempotency as every task above.
    # JWT_AUTO_ROTATION_INTERVAL_DAYS=0 (the default) makes every run a
    # guaranteed no-op -- this entry can stay registered unconditionally.
    "rotate-jwt-signing-key-daily-check": {
        "task": "api.tasks.jwt_key_rotation.rotate_jwt_signing_key",
        "schedule": crontab(hour=3, minute=45),
    },
    # Partie 1.4.3, item 5 -- same low-traffic window, offset again.
    # Idempotent: only acts on certificates actually due (see
    # api/tasks/ssl_certificate_renewal.py's own docstring).
    "check-ssl-renewals-daily": {
        "task": "api.tasks.ssl_certificate_renewal.check_ssl_renewals",
        "schedule": crontab(hour=4, minute=0),
    },
    "check-ssl-expirations-daily": {
        "task": "api.tasks.ssl_certificate_renewal.check_ssl_expirations",
        "schedule": crontab(hour=4, minute=15),
    },
    # Partie 1.4.4 -- a genuine fixed-interval poll (every
    # DOMAIN_VERIFICATION_INTERVAL_SECONDS, default 5 minutes), so a
    # plain timedelta rather than crontab's minute-matching, which is
    # built for "at these specific times of day" schedules like every
    # other entry above. Idempotent: only acts on domains genuinely
    # still `pending` (see api/tasks/domain_verification.py's own
    # docstring).
    "check-pending-domain-verifications": {
        "task": "api.tasks.domain_verification.check_pending_domain_verifications",
        "schedule": timedelta(seconds=settings.DOMAIN_VERIFICATION_INTERVAL_SECONDS),
    },
    # Partie 2.2.13 -- same low-traffic window, offset again. A real
    # HTTP HEAD request per document with a source_url is genuinely
    # cheap, but daily (not more frequent) avoids hammering external
    # sites this platform doesn't control.
    "check-modified-documents-daily": {
        "task": "api.tasks.document_modification_check.check_modified_documents_task",
        "schedule": crontab(hour=5, minute=0),
    },
    # Partie 2.2.14 -- same low-traffic window, offset again. Idempotent
    # by construction: detect_source_changes skips a source it cannot
    # confirm has changed often enough (see its own docstring), so
    # running this daily rather than more often is a real, deliberate
    # courtesy to the 5 external services this platform doesn't control.
    "sync-external-sources-daily": {
        "task": "api.tasks.external_source_sync.sync_all_sources_periodic_task",
        "schedule": crontab(hour=5, minute=15),
    },
    # Partie 2.2.15 -- a genuine fixed-interval poll (every minute), NOT
    # a daily crontab like every sweep above: a stored cron pattern can
    # legitimately be as fine-grained as "every minute" itself, so the
    # checker deciding what's due must run at least that often to honor
    # it -- same "timedelta, not crontab" reasoning as Partie 1.4.4's
    # own check-pending-domain-verifications entry.
    "check-scheduled-reindexes": {
        "task": "api.tasks.reindex_schedule.check_scheduled_reindexes_task",
        "schedule": timedelta(minutes=1),
    },
}

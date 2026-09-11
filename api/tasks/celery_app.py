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
from celery.signals import task_failure, task_success

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
        "api.tasks.reindex_schedule", "api.tasks.batch_jobs", "api.tasks.evaluation_jobs", "api.tasks.comparison_jobs",
        "api.tasks.deployment_evaluations", "api.tasks.conversation_cleanup", "api.tasks.voice_message_cleanup",
        "api.tasks.api_key_maintenance", "api.tasks.webhooks",
        "api.tasks.audit", "api.tasks.compliance", "api.tasks.security_scan", "api.tasks.billing", "api.tasks.alerting",
        "api.tasks.integrations", "api.tasks.plugins",
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
    # Partie 8.1.13 -- same low-traffic window, offset again. Idempotent
    # (see api/tasks/conversation_cleanup.py's own docstring).
    "purge-deleted-conversations-daily": {
        "task": "api.tasks.conversation_cleanup.purge_deleted_conversations_task",
        "schedule": crontab(hour=5, minute=30),
    },
    # Partie 8.2.7 -- same low-traffic window, offset again. Idempotent
    # (see api/tasks/voice_message_cleanup.py's own docstring).
    "purge-expired-voice-messages-daily": {
        "task": "api.tasks.voice_message_cleanup.purge_expired_voice_messages_task",
        "schedule": crontab(hour=5, minute=45),
    },
    # Partie 9.2.2/9.2.3/9.2.6 -- same low-traffic window, offset again.
    # All 4 real, idempotent (see api/tasks/api_key_maintenance.py's
    # own docstrings).
    "check-expiring-api-keys-daily": {
        "task": "api.tasks.api_key_maintenance.check_expiring_keys_task",
        "schedule": crontab(hour=6, minute=0),
    },
    "auto-remove-expired-api-keys-daily": {
        "task": "api.tasks.api_key_maintenance.auto_remove_expired_keys_task",
        "schedule": crontab(hour=6, minute=15),
    },
    # A genuine fixed-interval poll (every hour) rather than a daily
    # crontab -- a real, scheduled rotation set for e.g. "in 2 hours"
    # shouldn't have to wait until the next day's low-traffic window.
    "execute-scheduled-api-key-rotations": {
        "task": "api.tasks.api_key_maintenance.execute_scheduled_rotation_task",
        "schedule": timedelta(hours=1),
    },
    "reset-api-key-quotas-hourly": {
        "task": "api.tasks.api_key_maintenance.reset_quotas_task",
        "schedule": timedelta(hours=1),
    },
    # Partie 10.2 -- same low-traffic window, offset again. Idempotent
    # (see api/tasks/audit.py's own docstrings): safe on any schedule.
    "archive-old-audit-logs-daily": {
        "task": "api.tasks.audit.archive_logs",
        "schedule": crontab(hour=6, minute=30),
    },
    "purge-old-audit-logs-daily": {
        "task": "api.tasks.audit.purge_old_logs",
        "schedule": crontab(hour=6, minute=45),
    },
    # Partie 10.4 -- a real reminder sweep, not a purge (see
    # api/tasks/compliance.py's own docstring); daily is enough given
    # GDPR's own one-MONTH response deadline.
    "process-pending-data-requests-daily": {
        "task": "api.tasks.compliance.process_pending_data_requests",
        "schedule": crontab(hour=7, minute=0),
    },
    "generate-monthly-compliance-report": {
        "task": "api.tasks.compliance.generate_monthly_compliance_report",
        "schedule": crontab(hour=7, minute=15, day_of_month=1),
    },
    # Partie 10.5 -- real dependency scans across every organization,
    # same low-traffic window. Config: SECURITY_SCAN_SCHEDULE (informational).
    "run-scheduled-security-scans-daily": {
        "task": "api.tasks.security_scan.run_scheduled_security_scans",
        "schedule": crontab(hour=7, minute=30),
    },
    # Partie 12.4 -- real, idempotent (see api/tasks/billing.py's own
    # docstrings): a real invoice per genuinely-paid active subscription,
    # once a month; overdue-marking and reminders run daily.
    "generate-monthly-invoices": {
        "task": "api.tasks.billing.generate_monthly_invoices",
        "schedule": crontab(hour=2, minute=0, day_of_month=1),
    },
    "mark-overdue-invoices-daily": {
        "task": "api.tasks.billing.mark_overdue_invoices",
        "schedule": crontab(hour=7, minute=45),
    },
    "send-invoice-reminders-daily": {
        "task": "api.tasks.billing.send_invoice_reminders",
        "schedule": crontab(hour=8, minute=0),
    },
    "auto-refill-credits-daily": {
        "task": "api.tasks.billing.auto_refill_credits",
        "schedule": crontab(hour=8, minute=15),
    },
    # Partie 13.3 -- a genuine fixed-interval poll (real config:
    # ALERTING_CHECK_INTERVAL_SECONDS, default 60s), not a daily crontab
    # -- an alert rule breaching CPU/queue backlog needs to be caught
    # within a minute, not the next day's low-traffic window.
    "check-alert-rules": {
        "task": "api.tasks.alerting.check_alert_rules",
        "schedule": timedelta(seconds=settings.ALERTING_CHECK_INTERVAL_SECONDS),
    },
    # Partie 15.1 -- same low-traffic window, offset again.
    "cleanup-integration-logs-daily": {
        "task": "api.tasks.integrations.cleanup_integration_logs",
        "schedule": crontab(hour=8, minute=30),
    },
    # Partie 15.1/15.2 -- hourly, not daily: a failed inbound payload
    # (e.g. an external system's malformed field, fixed by an admin
    # updating the connection's mapping) should heal within the hour,
    # not wait for the next day's low-traffic window.
    "retry-failed-integration-syncs-hourly": {
        "task": "api.tasks.integrations.retry_failed_syncs",
        "schedule": crontab(minute=5),
    },
    "process-integration-webhooks-hourly": {
        "task": "api.tasks.integrations.process_integration_webhooks",
        "schedule": crontab(minute=35),
    },
    # Partie 15.3 -- every 6h: Airbyte connections created without their
    # own schedule configured directly in Airbyte still get synced.
    "sync-airbyte-integrations": {
        "task": "api.tasks.integrations.sync_integrations",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    # Partie 16 (ter) -- plugin marketplace periodic jobs.
    "validate-pending-plugins-hourly": {
        "task": "api.tasks.plugins.validate_pending_plugins",
        "schedule": crontab(minute=15),
    },
    "scan-plugin-security-daily": {
        "task": "api.tasks.plugins.scan_plugin_security",
        "schedule": crontab(hour=9, minute=0),
    },
    "cleanup-plugin-executions-daily": {
        "task": "api.tasks.plugins.cleanup_plugin_executions",
        "schedule": crontab(hour=9, minute=15),
    },
    "update-plugin-stats-hourly": {
        "task": "api.tasks.plugins.update_plugin_stats",
        "schedule": crontab(minute=45),
    },
}


# Partie 13.1 -- real Celery task outcome metrics, wired via Celery's
# own signals rather than per-task instrumentation: covers every task
# this app runs automatically, including ones added after this file.
@task_success.connect
def _on_task_success(sender=None, **kwargs):
    from api.monitoring import CELERY_TASKS_TOTAL

    CELERY_TASKS_TOTAL.labels(task_name=sender.name if sender else "unknown", outcome="success").inc()


@task_failure.connect
def _on_task_failure(sender=None, **kwargs):
    from api.monitoring import CELERY_TASKS_TOTAL

    CELERY_TASKS_TOTAL.labels(task_name=sender.name if sender else "unknown", outcome="failure").inc()

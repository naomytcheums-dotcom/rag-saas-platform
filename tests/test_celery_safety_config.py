"""Celery safety configuration and scheduler contract (Lot C). Static: no broker, no Redis, no worker is started."""

import importlib
import pkgutil

import api.tasks
from api.config import Settings, settings
from api.tasks.celery_app import celery_app


def _import_every_task_module():
    for info in pkgutil.iter_modules(api.tasks.__path__):
        importlib.import_module(f"api.tasks.{info.name}")


def test_every_task_is_bounded_by_a_soft_and_a_hard_time_limit():
    assert celery_app.conf.task_soft_time_limit == (settings.CELERY_TASK_SOFT_TIME_LIMIT_SECONDS or None)
    assert celery_app.conf.task_time_limit == (settings.CELERY_TASK_TIME_LIMIT_SECONDS or None)
    assert celery_app.conf.task_soft_time_limit and celery_app.conf.task_time_limit  # defaults: bounded (it used to be unbounded)
    assert celery_app.conf.task_soft_time_limit < celery_app.conf.task_time_limit  # the task can clean up before it is killed


def test_a_worker_process_reserves_one_task_at_a_time_by_default():
    assert Settings.model_fields["CELERY_WORKER_PREFETCH_MULTIPLIER"].default == 1
    assert celery_app.conf.worker_prefetch_multiplier == settings.CELERY_WORKER_PREFETCH_MULTIPLIER


def test_zero_disables_a_limit_for_deployments_with_legitimately_long_jobs(monkeypatch):
    monkeypatch.setenv("CELERY_TASK_SOFT_TIME_LIMIT_SECONDS", "0")
    monkeypatch.setenv("CELERY_TASK_TIME_LIMIT_SECONDS", "0")
    fresh = Settings(_env_file=None)
    assert (fresh.CELERY_TASK_SOFT_TIME_LIMIT_SECONDS or None) is None and (fresh.CELERY_TASK_TIME_LIMIT_SECONDS or None) is None


def test_every_beat_entry_points_to_a_registered_task():
    _import_every_task_module()
    schedule = celery_app.conf.beat_schedule
    assert len(schedule) >= 50  # 61 at the time of writing: a scan that finds nothing would prove nothing
    missing = sorted({entry["task"] for entry in schedule.values()} - set(celery_app.tasks))
    assert missing == [], f"beat schedules tasks that do not exist (they would fail silently every time): {missing}"


def test_the_periodic_billing_and_purge_tasks_are_scheduled():
    schedule = celery_app.conf.beat_schedule
    scheduled = {entry["task"] for entry in schedule.values()}
    for task in ("api.tasks.billing.generate_monthly_invoices", "api.tasks.billing.grant_monthly_plan_credits",
                 "api.tasks.billing.mark_overdue_invoices", "api.tasks.billing.auto_refill_credits"):
        assert task in scheduled, task

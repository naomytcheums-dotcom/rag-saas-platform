"""Spec 1.1.10 - the maintenance runner executes the daily tasks without a Celery worker."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location("run_maintenance_tasks", Path(__file__).resolve().parents[1] / "scripts" / "run_maintenance_tasks.py")
runner = importlib.util.module_from_spec(spec)
sys.modules["run_maintenance_tasks"] = runner
spec.loader.exec_module(runner)


def test_every_listed_task_resolves_to_a_real_callable():
    import importlib

    for name, (module, attribute) in runner.TASKS.items():
        assert callable(getattr(importlib.import_module(module), attribute)), name


def test_a_failing_task_does_not_stop_the_others(capsys):
    calls = []

    def fake_import(module):
        def boom():
            raise RuntimeError("database down")

        def fine():
            calls.append(module)
            return 3

        return SimpleNamespace(purge_deleted_accounts=boom, send_pending_deletion_reminders=fine)

    outcome = runner.run(["purge_deleted_accounts", "send_pending_deletion_reminders"], import_module=fake_import)
    assert outcome == {"purge_deleted_accounts": "failed: RuntimeError", "send_pending_deletion_reminders": "ok: 3"}
    assert calls == ["api.tasks.account_deletion_reminder"]


def test_an_unknown_task_name_is_reported_and_fails_the_run(capsys):
    assert runner.main(["no_such_task"]) == 1
    assert "no_such_task: failed: unknown task" in capsys.readouterr().out

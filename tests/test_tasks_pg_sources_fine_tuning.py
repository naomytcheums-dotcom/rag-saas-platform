"""Celery tasks of api/tasks/external_source_sync.py and api/tasks/fine_tuning.py against a real PostgreSQL.

The provider calls (a source's own import pipeline, the fine-tuning provider) are stubbed at the service boundary; what is checked here is the task layer: what it
selects, what it hands over, how it counts, how one failing item never aborts the sweep, and what it writes back."""

import datetime as dt
import uuid

import pytest
from sqlalchemy.orm import Session

from api.models.external_source import ExternalSource
from api.models.fine_tuning import FineTuningDataset, FineTuningJob, FineTuningJobStatus
from api.tasks import fine_tuning as fine_tuning_tasks
from api.tasks.external_source_sync import sync_all_sources_periodic_task, sync_all_sources_task, sync_source_task
from api.tasks.fine_tuning import (
    check_fine_tuning_status, cleanup_old_jobs, evaluate_fine_tuned_model, schedule_fine_tuning_job_submission, submit_fine_tuning_job,
)
from pg_tasks_support import organization, require_postgres

NOW = dt.datetime.now(dt.timezone.utc)


@pytest.fixture
def engine():
    return require_postgres()


# ------------------------------------------------------------------------------------------------ external sources


def test_syncing_one_source_returns_its_status_and_a_rejected_source_is_not_a_task_failure(monkeypatch):
    calls = []

    async def sync(db, source_id, triggered_by=None):
        calls.append((source_id, triggered_by))
        if str(source_id).startswith("00000000"):
            raise ValueError("source is disabled")
        return "idle"

    monkeypatch.setattr("api.tasks.external_source_sync.sync_external_source", sync)
    source, user = uuid.uuid4(), uuid.uuid4()

    assert sync_source_task(str(source), str(user)) == "idle"
    assert calls == [(source, user)]
    assert sync_source_task("00000000-0000-0000-0000-000000000001") == "rejected"


def test_syncing_a_whole_organization_passes_the_ids_through(monkeypatch):
    seen = []

    async def sync_all(db, organization_id, triggered_by=None):
        seen.append((organization_id, triggered_by))
        return {"synced": 2, "failed": 0}

    monkeypatch.setattr("api.tasks.external_source_sync.sync_all_sources", sync_all)
    org, user = uuid.uuid4(), uuid.uuid4()

    assert sync_all_sources_task(str(org), str(user)) == {"synced": 2, "failed": 0}
    sync_all_sources_task(str(org))
    assert seen == [(org, user), (org, None)]


def test_the_periodic_sweep_skips_unchanged_sources_counts_failures_and_survives_an_exception(engine, monkeypatch):
    with organization(engine, "sources") as org_id:
        with Session(engine) as db:
            sources = {name: ExternalSource(organization_id=org_id, source_type="url", source_id=f"https://example.test/{name}", enabled=name != "disabled") for name in ("changed", "unchanged", "failing", "crashing", "disabled")}
            db.add_all(sources.values())
            db.commit()
            ids = {name: source.id for name, source in sources.items()}
        synced = []

        async def changed(source):
            return source.id != ids["unchanged"]

        async def sync(db, source_id, triggered_by=None):
            synced.append(source_id)
            if source_id == ids["crashing"]:
                raise RuntimeError("network down")
            return "failed" if source_id == ids["failing"] else "idle"

        monkeypatch.setattr("api.tasks.external_source_sync.detect_source_changes", changed)
        monkeypatch.setattr("api.tasks.external_source_sync.sync_external_source", sync)

        result = sync_all_sources_periodic_task()

        assert ids["changed"] in synced and ids["failing"] in synced and ids["crashing"] in synced
        assert ids["unchanged"] not in synced and ids["disabled"] not in synced
        assert result["skipped"] >= 1 and result["failed"] >= 2 and result["synced"] >= 1 and result["checked"] >= 4


# ------------------------------------------------------------------------------------------------ fine-tuning


def _job(org_id, dataset_id, status, **fields) -> FineTuningJob:
    return FineTuningJob(organization_id=org_id, dataset_id=dataset_id, name="job", base_model="gpt-4o-mini", provider="openai", status=status, **fields)


def _dataset(org_id) -> FineTuningDataset:
    return FineTuningDataset(organization_id=org_id, name="ds", file_key=f"datasets/{uuid.uuid4().hex}.jsonl", size=10)


def test_submitting_a_job_returns_its_new_status_and_an_unknown_job_is_not_found(monkeypatch):
    from api.services.fine_tuning import FineTuningNotFoundError

    class Job:
        status = "running"

    async def submit(db, job_id):
        if str(job_id).startswith("00000000"):
            raise FineTuningNotFoundError("no such job")
        return Job()

    monkeypatch.setattr("api.services.fine_tuning.submit_job", submit)

    assert submit_fine_tuning_job(str(uuid.uuid4())) == "running"
    assert submit_fine_tuning_job("00000000-0000-0000-0000-000000000001") == "not_found"


def test_scheduling_a_submission_never_fails_the_request_when_the_broker_is_down(monkeypatch, caplog):
    queued = []
    monkeypatch.setattr(fine_tuning_tasks.submit_fine_tuning_job, "delay", lambda job_id: queued.append(job_id))
    job_id = uuid.uuid4()
    schedule_fine_tuning_job_submission(job_id)
    assert queued == [str(job_id)]

    def down(job_id):
        raise ConnectionError("broker down")

    monkeypatch.setattr(fine_tuning_tasks.submit_fine_tuning_job, "delay", down)
    schedule_fine_tuning_job_submission(job_id)
    assert "could not schedule submission" in caplog.text


def test_status_polling_covers_only_running_jobs_and_one_failure_does_not_stop_the_others(engine, monkeypatch):
    with organization(engine, "polling") as org_id:
        with Session(engine) as db:
            dataset = _dataset(org_id)
            db.add(dataset)
            db.flush()
            running_ok, running_bad, done = (_job(org_id, dataset.id, s) for s in (FineTuningJobStatus.running.value, FineTuningJobStatus.running.value, FineTuningJobStatus.succeeded.value))
            db.add_all([running_ok, running_bad, done])
            db.commit()
            ok_id, bad_id, done_id = running_ok.id, running_bad.id, done.id
        polled = []

        async def check(db, job_id):
            polled.append(job_id)
            if job_id == bad_id:
                raise RuntimeError("provider 502")

        monkeypatch.setattr("api.services.fine_tuning.check_job_status", check)

        assert check_fine_tuning_status() >= 1

        assert ok_id in polled and bad_id in polled and done_id not in polled


def test_evaluating_a_model_returns_the_evaluation_id(monkeypatch):
    evaluation_id = uuid.uuid4()
    received = []

    class Evaluation:
        id = evaluation_id

    async def evaluate(db, model_id, dataset_id, user_id):
        received.append((model_id, dataset_id, user_id))
        return Evaluation()

    monkeypatch.setattr("api.services.fine_tuning.evaluate_model", evaluate)
    model, dataset = uuid.uuid4(), uuid.uuid4()

    assert evaluate_fine_tuned_model(str(model), str(dataset)) == str(evaluation_id)
    assert received == [(model, dataset, None)]


def test_old_failed_or_cancelled_jobs_are_archived_never_deleted(engine):
    with organization(engine, "archive") as org_id:
        with Session(engine) as db:
            dataset = _dataset(org_id)
            db.add(dataset)
            db.flush()
            old_failed = _job(org_id, dataset.id, FineTuningJobStatus.failed.value, completed_at=NOW - dt.timedelta(days=120), metrics={"loss": 0.3})
            old_cancelled = _job(org_id, dataset.id, FineTuningJobStatus.cancelled.value, completed_at=NOW - dt.timedelta(days=120))
            recent_failed = _job(org_id, dataset.id, FineTuningJobStatus.failed.value, completed_at=NOW - dt.timedelta(days=5))
            old_succeeded = _job(org_id, dataset.id, FineTuningJobStatus.succeeded.value, completed_at=NOW - dt.timedelta(days=120))
            db.add_all([old_failed, old_cancelled, recent_failed, old_succeeded])
            db.commit()
            ids = [j.id for j in (old_failed, old_cancelled, recent_failed, old_succeeded)]

        assert cleanup_old_jobs() >= 2

        with Session(engine) as db:
            failed, cancelled, recent, succeeded = (db.get(FineTuningJob, i) for i in ids)
            assert failed.metrics == {"loss": 0.3, "archived": True}  # the existing metrics are kept
            assert cancelled.metrics.get("archived") is True
            assert "archived" not in recent.metrics and "archived" not in succeeded.metrics

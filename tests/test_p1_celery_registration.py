"""RAG-002 / RAG-003: every task module the API dispatches to must be registered with the worker, every scheduled task must exist,
a task published before its document committed is retried instead of reported as done, and documents whose task was lost are
re-dispatched by a periodic sweep.

Before: 11 task modules were missing from the Celery `include` list, so reindexing, ZIP/URL/sitemap/connector imports and batch uploads
were rejected by the worker ("Received unregistered task") while the API answered 200; and `process_document_task` reported
`not_found` as a success when it ran before the upload's transaction committed, leaving the document `pending` forever."""

import datetime as dt
import re
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from celery.exceptions import Retry
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from api.database import Base
from api.models.document import Document, DocumentStatus
from api.tasks.celery_app import celery_app

TASKS_DIR = Path(__file__).resolve().parent.parent / "api" / "tasks"
TASK_NAME = re.compile(r"""@celery_app\.task\(\s*name\s*=\s*["']([\w.]+)["']""")


def _task_modules():
    return sorted(p.stem for p in TASKS_DIR.glob("*.py") if not p.stem.startswith("_") and p.stem != "celery_app")


def test_every_task_module_is_in_the_celery_include_list():
    included = set(celery_app.conf.include)
    missing = [name for name in _task_modules() if f"api.tasks.{name}" not in included and TASK_NAME.search((TASKS_DIR / f"{name}.py").read_text(encoding="utf-8"))]
    assert not missing, f"task modules defining tasks but unknown to the worker: {missing}"


def test_every_declared_task_is_registered_once_the_worker_imports_its_modules():
    celery_app.loader.import_default_modules()
    declared = {name for module in _task_modules() for name in TASK_NAME.findall((TASKS_DIR / f"{module}.py").read_text(encoding="utf-8"))}
    unregistered = sorted(declared - set(celery_app.tasks))
    assert declared and not unregistered, f"declared but unregistered tasks: {unregistered}"


def test_every_scheduled_task_exists():
    celery_app.loader.import_default_modules()
    unknown = {key: entry["task"] for key, entry in celery_app.conf.beat_schedule.items() if entry["task"] not in celery_app.tasks}
    assert not unknown, f"beat schedules a task that no module defines: {unknown}"


@pytest.mark.parametrize("task_name", [
    "api.tasks.zip_import.process_zip_task", "api.tasks.reindex.reindex_document_task",
    "api.tasks.reindex.reindex_organization_documents_task", "api.tasks.google_drive_import.process_google_drive_task",
    "api.tasks.onedrive_import.process_onedrive_task",
])
def test_the_tasks_named_in_the_audit_are_registered(task_name):
    celery_app.loader.import_default_modules()
    assert task_name in celery_app.tasks


# ------------------------------------------------------------ RAG-003


def test_a_task_that_ran_before_the_upload_committed_is_retried_not_reported_as_done():
    from api.tasks import document_processing

    with patch.object(document_processing, "_process_document_async", AsyncMock(return_value="not_found")):
        with pytest.raises(Retry):
            document_processing.process_document_task.run(str(uuid.uuid4()))


def test_a_genuinely_deleted_document_stops_after_the_retries():
    from api.tasks import document_processing

    task = document_processing.process_document_task
    task.push_request(retries=task.max_retries)
    try:
        with patch.object(document_processing, "_process_document_async", AsyncMock(return_value="not_found")):
            assert task.run(str(uuid.uuid4())) == "not_found"
    finally:
        task.pop_request()


def test_a_processed_document_is_not_retried():
    from api.tasks import document_processing

    with patch.object(document_processing, "_process_document_async", AsyncMock(return_value="completed")):
        assert document_processing.process_document_task.run(str(uuid.uuid4())) == "completed"


def test_the_pending_sweep_is_scheduled():
    entry = celery_app.conf.beat_schedule["requeue-stale-pending-documents"]
    assert entry["task"] == "api.tasks.document_processing.requeue_stale_pending_documents_task"


async def test_the_sweep_redispatches_only_documents_stuck_pending(tmp_path, monkeypatch):
    from api.config import settings
    from api.security.documents import ZIP_CONTENT_TYPE
    from api.tasks import document_processing

    monkeypatch.setattr(settings, "DOCUMENT_PENDING_REQUEUE_AFTER_MINUTES", 10)
    url = f"sqlite+aiosqlite:///{tmp_path / 'sweep.db'}"
    setup = create_async_engine(url, poolclass=NullPool)
    async with setup.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    now = dt.datetime.now(dt.timezone.utc)
    org, user = uuid.uuid4(), uuid.uuid4()

    def doc(name, status, age_minutes, **kw):
        values = {"file_key": f"k/{name}", "file_type": "text/plain", "deleted_at": None, **kw}
        return Document(
            organization_id=org, created_by=user, name=name, file_size=1, status=status, created_at=now - dt.timedelta(minutes=age_minutes), **values,
        )

    stuck = doc("stuck.txt", DocumentStatus.pending.value, 30)
    rows = [
        stuck,
        doc("fresh.txt", DocumentStatus.pending.value, 1),
        doc("done.txt", DocumentStatus.completed.value, 90),
        doc("processing.txt", DocumentStatus.processing.value, 90),
        doc("deleted.txt", DocumentStatus.pending.value, 90, deleted_at=now),
        doc("nofile.txt", DocumentStatus.pending.value, 90, file_key=""),
        doc("archive.zip", DocumentStatus.pending.value, 90, file_type=ZIP_CONTENT_TYPE),
    ]
    async with async_sessionmaker(setup, expire_on_commit=False)() as session:
        session.add_all(rows)
        await session.commit()
    stuck_id = stuck.id
    await setup.dispose()

    monkeypatch.setattr(document_processing, "make_async_engine", lambda: create_async_engine(url, poolclass=NullPool))
    delay = MagicMock()
    monkeypatch.setattr(document_processing.process_document_task, "delay", delay)

    count = await document_processing._requeue_stale_pending_async()

    assert count == 1
    delay.assert_called_once_with(str(stuck_id))

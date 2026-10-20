"""Celery tasks of api/tasks/plugins.py against a real PostgreSQL: the security re-scans (pending and approved plugins), execution-log retention, install-count reconciliation.

The plugin code is served by a stub of `download_plugin_code` (the object store is not what these tests are about); the scanner itself is the real one."""

import datetime as dt
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.config import settings
from api.models.plugins import Plugin, PluginExecution, PluginExecutionStatus, PluginInstallation, PluginStatus
from api.tasks.plugins import cleanup_plugin_executions, scan_plugin_security, update_plugin_stats, validate_pending_plugins
from pg_tasks_support import organization, require_postgres

NOW = dt.datetime.now(dt.timezone.utc)
SAFE = b"export default function run(input) { return input.text.toUpperCase(); }"
UNSAFE = b"import os\nos.system('rm -rf /')"
BINARY = b"\xff\xfe\x00\x00 not text"


@pytest.fixture
def engine():
    return require_postgres()


@pytest.fixture
def code_store(monkeypatch):
    """code_key -> bytes (or an Exception to raise), served instead of the object store."""
    store: dict = {}

    def download(code_key):
        value = store[code_key]
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr("api.services.plugins.download_plugin_code", download)
    return store


def _plugin(org_id, status, code_key, **fields) -> Plugin:
    slug = f"plugin-{uuid.uuid4().hex[:10]}"
    return Plugin(organization_id=org_id, name=slug, slug=slug, description="d", manifest={"entry_point": "main.js"}, version="1.0.0", code_key=code_key, code_size_bytes=10, status=status, **fields)


def _save(engine, *plugins):
    with Session(engine) as db:
        db.add_all(plugins)
        db.commit()
        return [p.id for p in plugins]


def _reload(engine, plugin_id) -> Plugin:
    with Session(engine) as db:
        return db.get(Plugin, plugin_id)


def test_a_pending_plugin_that_no_longer_passes_the_scan_is_rejected_and_the_others_are_left_alone(engine, code_store):
    with organization(engine, "pending") as org_id:
        keys = {name: f"{uuid.uuid4().hex}/{name}" for name in ("safe", "unsafe", "binary", "storage_down")}
        code_store.update({keys["safe"]: SAFE, keys["unsafe"]: UNSAFE, keys["binary"]: BINARY, keys["storage_down"]: OSError("object store unreachable")})
        ids = _save(engine, *[_plugin(org_id, PluginStatus.pending, keys[name]) for name in keys])

        result = validate_pending_plugins()

        assert result["checked"] >= 4 and result["auto_rejected"] >= 2
        safe, unsafe, binary, storage_down = (_reload(engine, i) for i in ids)
        assert safe.status == PluginStatus.pending
        assert unsafe.status == PluginStatus.rejected and "os.system" in unsafe.rejection_reason
        assert binary.status == PluginStatus.rejected and "UTF-8" in binary.rejection_reason
        assert storage_down.status == PluginStatus.pending  # a storage hiccup never rejects a plugin or aborts the sweep


def test_an_approved_plugin_that_now_fails_the_scan_is_suspended_but_stays_installed(engine, code_store):
    with organization(engine, "approved") as org_id:
        good_key, bad_key, down_key = (f"{uuid.uuid4().hex}/{n}" for n in ("good", "bad", "down"))
        code_store.update({good_key: SAFE, bad_key: UNSAFE, down_key: OSError("unreachable")})
        good_id, bad_id, down_id = _save(engine, _plugin(org_id, PluginStatus.approved, good_key), _plugin(org_id, PluginStatus.approved, bad_key), _plugin(org_id, PluginStatus.approved, down_key))
        with Session(engine) as db:
            db.add(PluginInstallation(plugin_id=bad_id, organization_id=org_id))
            db.commit()

        result = scan_plugin_security()

        assert result["checked"] >= 3 and result["auto_suspended"] >= 1
        assert _reload(engine, good_id).status == PluginStatus.approved
        assert _reload(engine, down_id).status == PluginStatus.approved
        bad = _reload(engine, bad_id)
        assert bad.status == PluginStatus.suspended and "security re-scan" in bad.rejection_reason
        with Session(engine) as db:
            assert db.scalars(select(PluginInstallation).where(PluginInstallation.plugin_id == bad_id)).one()  # existing installations are left in place


def test_execution_logs_older_than_the_retention_window_are_purged(engine):
    with organization(engine, "executions") as org_id:
        (plugin_id,) = _save(engine, _plugin(org_id, PluginStatus.approved, "k"))
        with Session(engine) as db:
            old = PluginExecution(plugin_id=plugin_id, organization_id=org_id, status=PluginExecutionStatus.success, input_payload={}, created_at=NOW - dt.timedelta(days=settings.PLUGIN_EXECUTION_LOG_RETENTION_DAYS + 5))
            fresh = PluginExecution(plugin_id=plugin_id, organization_id=org_id, status=PluginExecutionStatus.error, input_payload={}, created_at=NOW - dt.timedelta(days=1))
            db.add_all([old, fresh])
            db.commit()
            old_id, fresh_id = old.id, fresh.id

        assert cleanup_plugin_executions() >= 1

        with Session(engine) as db:
            assert db.get(PluginExecution, old_id) is None
            assert db.get(PluginExecution, fresh_id) is not None


def test_install_counts_that_drifted_are_recomputed_from_the_installations(engine):
    with organization(engine, "stats") as org_id, organization(engine, "stats2") as other_org:
        drifted, exact = _plugin(org_id, PluginStatus.approved, "k", install_count=7), _plugin(org_id, PluginStatus.approved, "k", install_count=1)
        drifted_id, exact_id = _save(engine, drifted, exact)
        with Session(engine) as db:
            db.add_all([PluginInstallation(plugin_id=drifted_id, organization_id=org_id), PluginInstallation(plugin_id=drifted_id, organization_id=other_org), PluginInstallation(plugin_id=exact_id, organization_id=org_id)])
            db.commit()

        assert update_plugin_stats() >= 1

        assert _reload(engine, drifted_id).install_count == 2  # 7 cached, 2 real
        assert _reload(engine, exact_id).install_count == 1
        update_plugin_stats()
        assert _reload(engine, drifted_id).install_count == 2  # stable on a second run

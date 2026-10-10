"""Spec 13.3.8 - the migration tool knows the real head and can rehearse against the disposable PostgreSQL of the test run."""

import asyncio
import importlib.util
import os
import sys
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("migrate_tool", Path(__file__).resolve().parents[1] / "scripts" / "migrate.py")
tool = importlib.util.module_from_spec(spec)
sys.modules["migrate_tool"] = tool
spec.loader.exec_module(tool)


def test_head_revision_is_the_newest_migration_file():
    versions = sorted(p.name for p in (Path(__file__).resolve().parents[1] / "api" / "alembic" / "versions").glob("[0-9]*.py"))
    assert tool.head_revision() == versions[-1].split("_")[0]


def test_the_workflow_runs_this_tool_in_rehearsal_mode_by_default():
    workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "migrate.yml").read_text(encoding="utf-8")
    assert "scripts/migrate.py --apply" in workflow and "scripts/migrate.py;" in workflow.replace("\n", ";") or "else python scripts/migrate.py;" in workflow


@pytest.mark.skipif(not os.environ.get("DATABASE_URL", "").startswith("postgresql"), reason="needs the disposable PostgreSQL")
def test_a_database_already_at_head_passes_the_rehearsal():
    passed, current = asyncio.run(tool.rehearse(tool.database_url(), tool.head_revision()))
    assert passed and current == tool.head_revision()

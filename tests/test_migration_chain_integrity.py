"""Alembic chain integrity (Lot B), static -- no database needed: a single head, a linear history without gaps or forks, revision ids that match
their file names, and a pilot-RLS migration that only touches tables that exist, carry a uuid organization_id and already had RLS enabled.
The data-level proof (the whole chain applied on an empty PostgreSQL, round trip 0136 <-> 0137) was run on a disposable database and is
recorded in audit-reports/remediation-2026-10-10/04-database-migrations.md."""

import importlib.util
import re
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parent.parent
VERSIONS = ROOT / "api" / "alembic" / "versions"


def _script() -> ScriptDirectory:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "api" / "alembic"))
    return ScriptDirectory.from_config(config)


def test_there_is_exactly_one_head():
    assert len(_script().get_heads()) == 1


def test_the_history_is_linear_and_complete():
    script = _script()
    revisions = list(script.walk_revisions())
    files = sorted(VERSIONS.glob("[0-9]*.py"))
    assert len(revisions) == len(files)  # no file Alembic ignores, no duplicated revision id
    children: dict[str, int] = {}
    for revision in revisions:
        for parent in ([revision.down_revision] if isinstance(revision.down_revision, str) else list(revision.down_revision or ())):
            children[parent] = children.get(parent, 0) + 1
    assert [parent for parent, count in children.items() if count > 1] == []  # a fork would give two heads later


def test_every_revision_id_matches_its_file_number():
    for revision in _script().walk_revisions():
        prefix = Path(revision.path).name.split("_", 1)[0]
        assert revision.revision == prefix, f"{Path(revision.path).name} declares revision {revision.revision!r}"


def test_the_pilot_rls_migration_only_touches_real_tenant_tables():
    from sqlalchemy import Uuid

    import api.models  # noqa: F401  (registers every model)
    from api.database import Base

    spec = importlib.util.spec_from_file_location("m0137", VERSIONS / "0137_tenant_rls_policies_pilot.py")
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    history = "\n".join(path.read_text(encoding="utf-8") for path in sorted(VERSIONS.glob("[0-9]*.py")) if not path.name.startswith("0137"))
    for table in migration.PILOT_TABLES:
        assert table in Base.metadata.tables, table
        column = Base.metadata.tables[table].columns.get("organization_id")
        assert column is not None and isinstance(column.type, Uuid), f"{table}.organization_id must be a uuid column"
        assert re.search(rf"ENABLE ROW LEVEL SECURITY", history) and (table in history), f"{table}: no earlier migration mentions it"
    assert migration.down_revision == "0136"

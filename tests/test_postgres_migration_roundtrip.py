"""The whole Alembic chain, executed for real on a throw-away PostgreSQL database created by this module.

What it proves (and what a file-only check such as tests/test_migration_chain_contract.py cannot):
* the chain applies from an empty database to the single head;
* the newest migration goes down one step and back up, and the schema is then identical, column for column;
* every migration's `downgrade()` really undoes its `upgrade()`: down to an empty database and back to the head gives the same schema again.

The migrations run inside the test process (not in a subprocess), so their bodies are measured by coverage. Safety: the server must be the local one
the test settings already point at, and the database this module creates, then drops, has a name containing "test". No migration file is modified;
`alembic.ini` is not read, so the logging configuration of the test session is left untouched.
"""

import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from api.config import settings
from api.database_url import synchronous_database_url

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ROOT / "api" / "alembic" / "versions"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _alembic_config() -> Config:
    config = Config()  # no ini file: env.py then skips logging.config.fileConfig, which would reset the test session's loggers
    config.set_main_option("script_location", str(ROOT / "api" / "alembic"))
    return config


def _server_url():
    url = make_url(str(settings.DATABASE_URL))
    if not url.drivername.startswith("postgresql"):
        pytest.skip("needs a PostgreSQL DATABASE_URL (disposable): the fast suite runs on SQLite")
    if (url.host or "") not in LOCAL_HOSTS or "test" not in (url.database or ""):
        pytest.fail("refused: DATABASE_URL must be a local database whose name contains 'test' before this module creates and drops databases")
    return url


@pytest.fixture
def fresh_database(monkeypatch):
    """A new, empty database on the test server, used as the migration target for one test, then dropped."""
    server = _server_url()
    admin = create_engine(synchronous_database_url(server.set(database="postgres")), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        admin.dispose()
        pytest.skip(f"PostgreSQL is not reachable ({type(exc).__name__})")
    name = f"rag_migtest_{uuid.uuid4().hex[:10]}"
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    target = server.set(database=name)
    monkeypatch.setattr(settings, "DATABASE_URL", target.render_as_string(hide_password=False))
    engine = create_engine(synchronous_database_url(target))
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


def _version(engine) -> str | None:
    with engine.connect() as connection:
        exists = connection.execute(text("SELECT to_regclass('public.alembic_version')")).scalar()
        return connection.execute(text("SELECT version_num FROM alembic_version")).scalar() if exists else None


_SNAPSHOT_QUERIES = {
    "tables": """SELECT c.relname, c.relkind, c.relrowsecurity, c.relforcerowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                 WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'm', 'S') ORDER BY 1""",
    "columns": """SELECT c.relname, a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull, pg_get_expr(d.adbin, d.adrelid)
                  FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid JOIN pg_namespace n ON n.oid = c.relnamespace
                  LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
                  WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') AND a.attnum > 0 AND NOT a.attisdropped ORDER BY 1, 2""",
    "constraints": """SELECT c.relname, k.conname, k.contype, pg_get_constraintdef(k.oid) FROM pg_constraint k JOIN pg_class c ON c.oid = k.conrelid
                      JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'public' ORDER BY 1, 2""",
    "indexes": "SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' ORDER BY 1, 2",
    "policies": "SELECT tablename, policyname, cmd, roles::text, qual, with_check FROM pg_policies WHERE schemaname = 'public' ORDER BY 1, 2",
    "enums": """SELECT t.typname, e.enumlabel, e.enumsortorder FROM pg_type t JOIN pg_enum e ON e.enumtypid = t.oid
                JOIN pg_namespace n ON n.oid = t.typnamespace WHERE n.nspname = 'public' ORDER BY 1, 3""",
    "triggers": """SELECT c.relname, t.tgname, pg_get_triggerdef(t.oid) FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
                   JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'public' AND NOT t.tgisinternal ORDER BY 1, 2""",
    "functions": """SELECT p.proname, pg_get_function_identity_arguments(p.oid), md5(pg_get_functiondef(p.oid)) FROM pg_proc p
                    JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = 'public' AND p.prokind = 'f'
                    AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = p.oid AND d.deptype = 'e') ORDER BY 1, 2""",
    "extensions": "SELECT extname FROM pg_extension ORDER BY 1",
}


def schema_snapshot(engine) -> dict[str, list[tuple]]:
    """Everything the migrations create in `public`, in a comparable form (names, types, nullability, defaults, constraints, indexes, policies...)."""
    with engine.connect() as connection:
        return {name: [tuple(row) for row in connection.execute(text(query))] for name, query in _SNAPSHOT_QUERIES.items()}


def _differences(before: dict, after: dict) -> dict[str, dict[str, list]]:
    out = {}
    for key in before:
        lost, gained = sorted(set(before[key]) - set(after[key])), sorted(set(after[key]) - set(before[key]))
        if lost or gained:
            out[key] = {"lost": lost[:10], "gained": gained[:10]}
    return out


def test_the_chain_has_a_single_head_and_it_is_the_newest_migration_file():
    heads = ScriptDirectory.from_config(_alembic_config()).get_heads()
    newest = max(path.name.split("_", 1)[0] for path in VERSIONS.glob("[0-9][0-9][0-9][0-9]_*.py"))
    assert heads == [newest], heads


def test_the_chain_applies_from_an_empty_database_to_the_head(fresh_database):
    head = ScriptDirectory.from_config(_alembic_config()).get_current_head()
    assert _version(fresh_database) is None
    command.upgrade(_alembic_config(), "head")
    assert _version(fresh_database) == head
    snapshot = schema_snapshot(fresh_database)
    tables = {row[0] for row in snapshot["tables"] if row[1] == "r"}
    assert {"organizations", "users", "documents", "plans", "subscriptions", "invoices", "credits"} <= tables
    assert ("vector",) in snapshot["extensions"]
    assert all(row[2] for row in snapshot["tables"] if row[1] == "r" and row[0] != "alembic_version"), "a table without row level security"


def test_the_newest_migration_goes_down_one_step_and_back_to_an_identical_schema(fresh_database):
    script = ScriptDirectory.from_config(_alembic_config())
    head = script.get_current_head()
    previous = script.get_revision(head).down_revision
    command.upgrade(_alembic_config(), "head")
    at_head = schema_snapshot(fresh_database)

    command.downgrade(_alembic_config(), "-1")
    assert _version(fresh_database) == previous
    one_down = schema_snapshot(fresh_database)
    assert one_down != at_head, "the newest downgrade() changed nothing"

    command.upgrade(_alembic_config(), "head")
    assert _version(fresh_database) == head
    assert _differences(at_head, schema_snapshot(fresh_database)) == {}


def test_every_migration_reverses_down_to_an_empty_database_and_back_to_an_identical_schema(fresh_database):
    head = ScriptDirectory.from_config(_alembic_config()).get_current_head()
    command.upgrade(_alembic_config(), "head")
    at_head = schema_snapshot(fresh_database)

    command.downgrade(_alembic_config(), "base")
    assert _version(fresh_database) is None
    leftovers = [row[0] for row in schema_snapshot(fresh_database)["tables"] if row[0] != "alembic_version"]
    assert leftovers == [], f"objects left behind after downgrading every migration: {leftovers}"

    command.upgrade(_alembic_config(), "head")
    assert _version(fresh_database) == head
    assert _differences(at_head, schema_snapshot(fresh_database)) == {}

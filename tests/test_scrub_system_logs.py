"""scripts/scrub_system_logs.py: masks the secrets already stored in system_logs. Throw-away SQLite file; the real database is never touched."""

import importlib.util
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
SECRETS = ("hunter22secret", "S3cr3tPw", "abc123def456ghi789")


def _load():
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("scrub_system_logs", ROOT / "scripts" / "scrub_system_logs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'logs.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE system_logs (id TEXT PRIMARY KEY, level TEXT NOT NULL, message TEXT NOT NULL)"))
        rows = [
            ("ERROR", "login failed password=hunter22secret for user 12"),
            ("ERROR", "could not connect to postgresql://app:S3cr3tPw@db.example.com:5432/x"),
            ("WARNING", "calling the API with Authorization: Bearer abc123def456ghi789"),
            ("ERROR", "processing document 8f1c2d3e for organization 12"),
            ("WARNING", "context window limit reached: 4096"),
        ]
        for i, (level, message) in enumerate(rows):
            conn.execute(text("INSERT INTO system_logs (id, level, message) VALUES (:i, :l, :m)"), {"i": f"{i:08d}-{uuid.uuid4().hex[:8]}", "l": level, "m": message})
    yield engine
    engine.dispose()


def _messages(engine):
    with engine.connect() as conn:
        return [row[0] for row in conn.execute(text("SELECT message FROM system_logs ORDER BY id"))]


def test_a_dry_run_counts_and_writes_nothing(engine):
    before = _messages(engine)
    result = _load().scrub(engine, apply=False, batch_size=2)
    assert result == {"scanned": 5, "affected": 3, "updated": 0, "by_level": {"ERROR": 2, "WARNING": 1}}
    assert _messages(engine) == before


def test_apply_masks_only_the_rows_that_hold_a_secret_and_a_second_pass_finds_nothing(engine):
    module = _load()
    before = _messages(engine)
    result = module.scrub(engine, apply=True, batch_size=2)
    assert result["affected"] == 3 and result["updated"] == 3
    after = _messages(engine)
    assert not any(secret in message for message in after for secret in SECRETS)
    assert after[3:] == before[3:]  # ordinary rows are byte for byte unchanged
    assert module.scrub(engine, apply=False)["affected"] == 0


def test_the_command_refuses_apply_without_the_exact_database_name_and_never_prints_a_message(tmp_path, monkeypatch, capsys):
    from api.config import settings

    database = tmp_path / "cmd.db"
    engine = create_engine(f"sqlite:///{database}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE system_logs (id TEXT PRIMARY KEY, level TEXT NOT NULL, message TEXT NOT NULL)"))
        conn.execute(text("INSERT INTO system_logs VALUES ('1', 'ERROR', 'login failed password=hunter22secret')"))
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{database}")
    module = _load()
    assert module.main(["--apply"]) == 2
    assert module.main(["--apply", "--confirm-database", "somewhere-else"]) == 2
    with engine.connect() as conn:
        assert "hunter22secret" in conn.execute(text("SELECT message FROM system_logs")).scalar()  # still untouched
    capsys.readouterr()
    assert module.main([]) == 0  # dry run
    assert "hunter22secret" not in capsys.readouterr().out
    assert module.main(["--apply", "--confirm-database", str(database)]) == 0
    with engine.connect() as conn:
        assert "hunter22secret" not in conn.execute(text("SELECT message FROM system_logs")).scalar()

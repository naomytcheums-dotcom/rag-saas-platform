"""Exercise deployment script failures with Docker and Git stubbed out."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy.engine import URL

from scripts.staging_target import isolated_environment

ROOT = Path(__file__).resolve().parent.parent
HEALTHCHECK_ATTEMPTS = "2"


def _bash():
    if sys.platform == "win32":
        bash = r"C:\Program Files\Git\bin\bash.exe"
    else:
        bash = shutil.which("bash")
    if not bash or not Path(bash).is_file():
        pytest.fail("Bash is required for deployment script tests.")
    return bash


def _test_environment():
    loopback_url = URL.create(
        "postgresql+asyncpg",
        username="test",
        password="test",
        host="127.0.0.1",
        port=1,
        database="test",
    )
    env = isolated_environment(loopback_url)
    env["POSTGRES_HEALTHCHECK_MAX_ATTEMPTS"] = HEALTHCHECK_ATTEMPTS
    return env


def _run_script(script, tmp_path, stubs):
    (tmp_path / ".env").write_text("test-only placeholder\n", encoding="utf-8")
    source = (ROOT / script).read_text(encoding="utf-8")
    return subprocess.run(
        [_bash(), "--noprofile", "--norc", "-c", stubs + "\n" + source],
        cwd=tmp_path,
        env=_test_environment(),
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )


@pytest.mark.parametrize("script", ["install.sh", "update.sh"])
def test_unhealthy_postgres_fails_after_bounded_checks_without_migrating(
    script, tmp_path
):
    (tmp_path / "docker-calls").write_text("", encoding="utf-8")
    stubs = """
docker() {
  printf '%s\\n' "$*" >> docker-calls
  case "$*" in *pg_isready*) return 1 ;; esac
  return 0
}
git() { return 0; }
sleep() { :; }
"""
    if script == "update.sh":
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        backup = scripts_dir / "backup.sh"
        backup.write_text(
            "#!/usr/bin/env bash\n"
            "echo 'Backup written to backups/test.sql.gz'\n",
            encoding="utf-8",
        )
        os.chmod(backup, 0o755)

    result = _run_script(script, tmp_path, stubs)

    assert result.returncode != 0
    assert "did not become healthy after 2 checks" in result.stderr
    calls = (tmp_path / "docker-calls").read_text(encoding="utf-8").splitlines()
    assert sum("pg_isready" in call for call in calls) == 2
    assert not any("alembic upgrade head" in call for call in calls)


def test_invalid_healthcheck_attempt_count_fails_before_polling(tmp_path):
    (tmp_path / "docker-calls").write_text("", encoding="utf-8")
    stubs = """
docker() {
  printf '%s\\n' "$*" >> docker-calls
  return 0
}
git() { return 0; }
sleep() { :; }
"""
    env = _test_environment()
    env["POSTGRES_HEALTHCHECK_MAX_ATTEMPTS"] = "0"
    source = (ROOT / "install.sh").read_text(encoding="utf-8")

    result = subprocess.run(
        [_bash(), "--noprofile", "--norc", "-c", stubs + "\n" + source],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert result.returncode != 0
    assert "must be a positive integer" in result.stderr
    calls = (tmp_path / "docker-calls").read_text(encoding="utf-8").splitlines()
    assert not any("pg_isready" in call for call in calls)
    assert not any("alembic upgrade head" in call for call in calls)

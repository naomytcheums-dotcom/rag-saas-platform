"""Run backup/restore shell logic with Docker replaced; never contact a database."""

import gzip
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _run_script(script, tmp_path, stub, arguments, confirmation=""):
    if sys.platform == "win32":
        bash = r"C:\Program Files\Git\bin\bash.exe"
    else:
        bash = shutil.which("bash")
    if not bash or not Path(bash).is_file():
        pytest.fail("Bash is required for backup/restore shell tests.")
    source = (ROOT / "scripts" / script).read_text(encoding="utf-8")
    command = (
        "export BACKUP_S3_ENABLED=false BACKUP_RETENTION_DAYS=0\n"
        + stub + '\nset -- ' + arguments + "\n" + source
    )
    return subprocess.run(
        [bash, "--noprofile", "--norc", "-c", command],
        cwd=tmp_path,
        input=confirmation,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )


def test_failed_dump_does_not_publish_or_retain_partial_backup(tmp_path):
    result = _run_script(
        "backup.sh", tmp_path,
        "docker() { printf 'partial SQL'; return 1; }", "backups",
    )
    assert result.returncode != 0
    assert list((tmp_path / "backups").iterdir()) == []
    assert "Backup written" not in result.stdout


def test_successful_dump_publishes_valid_gzip(tmp_path):
    result = _run_script(
        "backup.sh", tmp_path,
        "docker() { printf 'SELECT 1;'; }", "backups",
    )
    assert result.returncode == 0, result.stderr
    files = list((tmp_path / "backups").iterdir())
    assert len(files) == 1
    assert gzip.decompress(files[0].read_bytes()) == b"SELECT 1;"


def test_backup_collision_does_not_overwrite_previous_dump(tmp_path):
    directory = tmp_path / "backups"
    directory.mkdir()
    original = directory / "backup_fixed.sql.gz"
    original.write_bytes(gzip.compress(b"previous dump"))
    result = _run_script(
        "backup.sh", tmp_path,
        "date() { printf 'fixed'; }\ndocker() { printf 'new dump'; }", "backups",
    )
    assert result.returncode != 0
    assert gzip.decompress(original.read_bytes()) == b"previous dump"
    assert list(directory.iterdir()) == [original]


def test_corrupt_archive_is_rejected_before_docker_or_confirmation(tmp_path):
    (tmp_path / "input.sql.gz").write_bytes(b"not a gzip archive")
    result = _run_script(
        "restore.sh", tmp_path,
        "docker() { touch docker-called; }", "input.sql.gz", "\n",
    )
    assert result.returncode != 0
    assert not (tmp_path / "docker-called").exists()
    assert "Press Ctrl+C" not in result.stdout


@pytest.mark.parametrize("sql_failure", [False, True])
def test_restore_stops_on_sql_error_and_reports_only_success(tmp_path, sql_failure):
    (tmp_path / "input.sql.gz").write_bytes(gzip.compress(b"SELECT 1;"))
    stub = (
        'docker() { printf "%s\\n" "$*" > docker-args; cat >/dev/null; '
        'case "$*" in *ON_ERROR_STOP=1*) '
        + ("return 3" if sql_failure else "return 0")
        + ";; *) return 0;; esac; }"
    )
    result = _run_script("restore.sh", tmp_path, stub, "input.sql.gz", "\n")
    assert "ON_ERROR_STOP=1" in (tmp_path / "docker-args").read_text()
    assert result.returncode == (3 if sql_failure else 0)
    assert ("Restore complete." in result.stdout) is not sql_failure

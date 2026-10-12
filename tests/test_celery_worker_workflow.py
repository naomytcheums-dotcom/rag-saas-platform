"""Exercise the scheduled worker's shell exit handling without starting Celery."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent


def _bash() -> str:
    if sys.platform == "win32":
        git = shutil.which("git")
        git_bash = (
            Path(git).resolve().parent.parent / "bin" / "bash.exe"
            if git else Path(r"C:\Program Files\Git\bin\bash.exe")
        )
        bash = str(git_bash) if git_bash.is_file() else None
    else:
        bash = shutil.which("bash")
    if bash is None:
        pytest.fail("Bash is required to validate the Linux worker workflow.")
    return bash


def _step() -> dict:
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "celery-worker.yml").read_text(encoding="utf-8")
    )
    return next(
        step for step in workflow["jobs"]["drain-queue"]["steps"]
        if step.get("name") == "Run Celery worker for a bounded window"
    )


def _run_step(worker_status: int, env: dict | None = None, prelude: str = "") -> subprocess.CompletedProcess:
    # The script also starts `celery ... beat` in the background: a function shadows any real celery executable, so nothing is started.
    stub = f'timeout() {{ return {worker_status}; }}\ncelery() {{ return 0; }}\n'
    return subprocess.run(
        [_bash(), "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", prelude + stub + _step()["run"]],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
        env=env,
    )


def test_the_exit_handling_check_never_starts_a_celery_process(tmp_path):
    """The workflow also starts `celery ... beat` in the background (PROD-001) and the check only stubs `timeout`: a real beat was
    started against whatever broker the environment names. The script kills it right away, so it normally dies before doing
    anything, but when it survives (it keeps the output pipes open past the 10 s limit) the check fails intermittently. `kill` is
    delayed here so that a process that really is started has the time to leave its trace."""
    marker = tmp_path / "celery-was-called.txt"
    shim_dir = tmp_path / "bin"
    shim_dir.mkdir()
    shim = shim_dir / "celery"
    shim.write_text('#!/bin/sh\necho "$@" >> "$SHIM_MARKER"\nexit 0\n', encoding="utf-8")
    shim.chmod(0o755)
    env = {**os.environ, "PATH": str(shim_dir) + os.pathsep + os.environ.get("PATH", ""), "SHIM_MARKER": str(marker)}
    _run_step(0, env=env, prelude='kill() { sleep 2; builtin kill "$@"; }\n')
    assert not marker.exists(), f"the exit-handling check started celery: {marker.read_text(encoding='utf-8')}"


@pytest.mark.parametrize("worker_status", [0, 1, 2, 124, 125, 126, 127, 137, 143])
def test_worker_workflow_propagates_failures(worker_status):
    step = _step()
    result = _run_step(worker_status)
    assert result.returncode == (0 if worker_status in {0, 124} else worker_status), result.stderr
    assert ("::error::" in result.stdout) == (worker_status not in {0, 124})
    assert "--signal=TERM --kill-after=60" in step["run"]

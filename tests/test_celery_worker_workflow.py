"""Exercise the scheduled worker's shell exit handling without starting Celery."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("worker_status", [0, 1, 2, 124, 125, 126, 127, 137, 143])
def test_worker_workflow_propagates_failures(worker_status):
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
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "celery-worker.yml").read_text(encoding="utf-8")
    )
    step = next(
        step for step in workflow["jobs"]["drain-queue"]["steps"]
        if step.get("name") == "Run Celery worker for a bounded window"
    )
    stub = f'timeout() {{ return {worker_status}; }}\n'
    result = subprocess.run(
        [bash, "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", stub + step["run"]],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == (0 if worker_status in {0, 124} else worker_status), result.stderr
    assert ("::error::" in result.stdout) == (worker_status not in {0, 124})
    assert "--signal=TERM --kill-after=60" in step["run"]

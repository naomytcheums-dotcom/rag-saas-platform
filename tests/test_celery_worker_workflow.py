"""Exercise the scheduled worker's shell exit handling without starting Celery."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent


def _find_bash():
    r"""A POSIX bash able to run the workflow step.

    Linux/macOS: the first bash on PATH. Windows: Git for Windows' bash, found from wherever git.exe lives. `shutil.which("git")` returns
    `...\Git\cmd\git.exe` or, when Git's mingw64 directory comes first on PATH (Git Bash, many dev shells), `...\Git\mingw64\bin\git.exe`: the
    install root is therefore found by walking up the parents until `bin\bash.exe` exists, not by a fixed `parent.parent`. `C:\Windows\System32\bash.exe`
    is the WSL launcher, not a bash for these scripts, so it is never used."""
    if sys.platform != "win32":
        return shutil.which("bash")
    roots = []
    git = shutil.which("git")
    if git:
        roots.extend(Path(git).resolve().parents)
    for var in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.environ.get(var)
        if base:
            roots.append(Path(base) / "Git")
            roots.append(Path(base) / "Programs" / "Git")
    for root in roots:
        for rel in ("bin/bash.exe", "usr/bin/bash.exe"):
            candidate = root / rel
            if candidate.is_file():
                return str(candidate)
    return None


@pytest.mark.parametrize("worker_status", [0, 1, 2, 124, 125, 126, 127, 137, 143])
def test_worker_workflow_propagates_failures(worker_status):
    bash = _find_bash()
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

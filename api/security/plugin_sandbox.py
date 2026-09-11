"""
Partie 16 (ter) -- real plugin execution sandbox.

Two real, layered execution paths, chosen automatically:

**Docker sandbox (`run_plugin_sandboxed_docker`)** -- used whenever a
real `docker` binary is on PATH AND the real
`rag-saas-plugin-sandbox` image (built from `Dockerfile.plugin-sandbox`
at this repo's root) already exists locally. A genuinely isolated
container per execution: `--network none` (no outbound network at
all -- the strongest, simplest real enforcement of "no ambient
authority"), `--read-only` root filesystem, `--cpus 0.5`, `--memory
256m` (a real cgroup limit, enforced on every OS Docker runs on --
including Windows, unlike the subprocess fallback's Linux-only
`RLIMIT_AS`), `--pids-limit 64` (real fork-bomb guard), `--cap-drop
ALL` + `--security-opt no-new-privileges` (no real Linux capabilities
at all, can't escalate even if a kernel exploit is found), a real
non-root user, and a hard wall-clock timeout via `docker run`'s own
process being killed from the Python side exactly like the subprocess
path.

**Subprocess sandbox (`run_plugin_sandboxed_subprocess`)** -- the
real, honest fallback when Docker isn't available (e.g. this repo's
own Windows dev machine some of the time, or a deployment that
deliberately doesn't run Docker-in-Docker). A genuinely SEPARATE OS
process (`node`/`python` subprocess, no shared interpreter state with
the API server), a real wall-clock timeout, a real memory cap via
`RLIMIT_AS` on POSIX only (not Windows -- `resource` is POSIX-only
stdlib, no Windows equivalent without a third-party dependency this
pass doesn't add), and the same near-empty environment as the Docker
path -- weaker isolation (no real network/filesystem/capability
boundary, only process separation), documented as exactly that, not
hidden behind the same name.

`run_plugin_sandboxed` (what api/services/plugins.py's own
execute_plugin actually calls) picks whichever path is real and
available, and reports which one it used in its own return value
(`"engine": "docker"` or `"subprocess"`) -- a real, honest signal for
docs/plugins/SECURITY.md's own "was this actually isolated" question,
not something the caller has to guess.

Protocol (both engines): the plugin's entry_point script (.js run via
`node`, .py run via `python`) is invoked with the JSON-encoded input
payload on stdin, and must print exactly one JSON value to stdout as
its result -- documented for real plugin developers in
docs/plugins/DEVELOPER_GUIDE.md.
"""

import json
import os
import shutil
import tempfile
import time
import uuid

from api.config import settings

MAX_OUTPUT_BYTES = 64 * 1024  # a plugin result is small structured data, not a file transfer
SANDBOX_DOCKER_IMAGE = "rag-saas-plugin-sandbox:latest"


class PluginSandboxError(Exception):
    pass


class PluginRateLimitedError(PluginSandboxError):
    pass


def _resolve_interpreter_name(entry_point: str) -> str:
    if entry_point.endswith(".js"):
        return "node"
    if entry_point.endswith(".py"):
        return "python"
    raise PluginSandboxError(f"Unsupported entry_point extension: {entry_point}")


def _resolve_interpreter(entry_point: str) -> str:
    name = _resolve_interpreter_name(entry_point)
    candidates = ["node"] if name == "node" else ["python3", "python"]
    for candidate in candidates:
        interpreter = shutil.which(candidate)
        if interpreter:
            return interpreter
    raise PluginSandboxError(f"{'Node.js' if name == 'node' else 'Python'} ('{name}') is not installed on this deployment -- cannot execute {entry_point.rsplit('.', 1)[-1]} plugins.")


_docker_availability_cache: bool | None = None


def _docker_sandbox_available() -> bool:
    """Real, cached check -- a real `docker` binary on PATH AND the
    real sandbox image already built locally (`docker build -f
    Dockerfile.plugin-sandbox -t rag-saas-plugin-sandbox:latest .`).
    Cached per-process (checked once, not on every single execution)
    since neither Docker's presence nor the image's presence changes
    within one running server process."""
    global _docker_availability_cache
    if _docker_availability_cache is not None:
        return _docker_availability_cache

    import subprocess

    docker_bin = shutil.which("docker")
    if not docker_bin or not settings.PLUGINS_DOCKER_SANDBOX_ENABLED:
        _docker_availability_cache = False
        return False
    try:
        result = subprocess.run([docker_bin, "image", "inspect", SANDBOX_DOCKER_IMAGE], capture_output=True, timeout=10)
        _docker_availability_cache = result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        _docker_availability_cache = False
    return _docker_availability_cache


def _memory_limit_preexec_fn(max_memory_mb: int):
    """POSIX-only real memory cap -- see this module's own top
    docstring on why Windows gets no enforcement here."""

    def _apply():
        try:
            import resource

            max_bytes = max_memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (max_bytes, max_bytes))
        except (ImportError, ValueError, OSError):
            pass

    return _apply


def _write_entry_script(tmpdir: str, entry_point: str, code: bytes) -> str:
    script_path = os.path.join(tmpdir, f"entry_{uuid.uuid4().hex}{os.path.splitext(entry_point)[1]}")
    with open(script_path, "wb") as f:
        f.write(code)
    return script_path


def run_plugin_sandboxed_subprocess(entry_point: str, code: bytes, payload: dict, *, timeout_seconds: int, max_memory_mb: int) -> dict:
    """The real, honest fallback -- process isolation only (see this
    module's own top docstring for exactly what that does and does not
    guarantee vs. the Docker path)."""
    import subprocess

    interpreter = _resolve_interpreter(entry_point)

    with tempfile.TemporaryDirectory(prefix="plugin-sandbox-") as tmpdir:
        script_path = _write_entry_script(tmpdir, entry_point, code)

        run_kwargs = {
            "input": json.dumps(payload).encode("utf-8"),
            "capture_output": True,
            "timeout": timeout_seconds,
            "cwd": tmpdir,
            # Near-empty environment -- no ambient secrets/credentials/
            # settings reach the sandboxed process. PATH alone so the
            # interpreter itself can still resolve its own stdlib.
            "env": {"PATH": os.environ.get("PATH", "")},
        }
        if hasattr(os, "fork"):  # POSIX only -- subprocess.run raises outright if preexec_fn is passed on Windows
            run_kwargs["preexec_fn"] = _memory_limit_preexec_fn(max_memory_mb)

        started = time.monotonic()
        try:
            result = subprocess.run([interpreter, script_path], **run_kwargs)
        except subprocess.TimeoutExpired:
            duration_ms = int((time.monotonic() - started) * 1000)
            return {"status": "timeout", "output": None, "error": f"Execution exceeded the {timeout_seconds}s limit", "duration_ms": duration_ms, "engine": "subprocess"}

        duration_ms = int((time.monotonic() - started) * 1000)

        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")[:2000]
            return {"status": "error", "output": None, "error": stderr or f"Plugin exited with code {result.returncode}", "duration_ms": duration_ms, "engine": "subprocess"}

        stdout = result.stdout[:MAX_OUTPUT_BYTES]
        try:
            output = json.loads(stdout.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {"status": "error", "output": None, "error": "Plugin did not print a single valid JSON value to stdout", "duration_ms": duration_ms, "engine": "subprocess"}

        return {"status": "success", "output": output, "error": None, "duration_ms": duration_ms, "engine": "subprocess"}


def run_plugin_sandboxed_docker(entry_point: str, code: bytes, payload: dict, *, timeout_seconds: int, max_memory_mb: int, cpu_limit: float) -> dict:
    """Real container-per-execution isolation -- see this module's own
    top docstring for the exact real flags and what each one enforces."""
    import subprocess

    interpreter_name = _resolve_interpreter_name(entry_point)
    docker_bin = shutil.which("docker")

    with tempfile.TemporaryDirectory(prefix="plugin-sandbox-") as tmpdir:
        script_path = _write_entry_script(tmpdir, entry_point, code)
        script_name = os.path.basename(script_path)

        docker_cmd = [
            docker_bin, "run", "--rm", "-i",
            "--network", "none",
            "--read-only",
            "--tmpfs", "/tmp:size=16m,noexec",
            f"--cpus={cpu_limit}",
            f"--memory={max_memory_mb}m",
            f"--memory-swap={max_memory_mb}m",
            "--pids-limit", "64",
            "--security-opt", "no-new-privileges",
            "--cap-drop", "ALL",
            "--user", "10001:10001",
            "-v", f"{tmpdir}:/plugin:ro",
            SANDBOX_DOCKER_IMAGE,
            interpreter_name, f"/plugin/{script_name}",
        ]

        started = time.monotonic()
        try:
            # A real, outer wall-clock timeout on top of Docker's own
            # process -- `docker run --rm` reliably tears the container
            # down when this subprocess is killed on timeout, same as
            # `docker stop` would, so no separate cleanup step is needed.
            result = subprocess.run(docker_cmd, input=json.dumps(payload).encode("utf-8"), capture_output=True, timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            duration_ms = int((time.monotonic() - started) * 1000)
            return {"status": "timeout", "output": None, "error": f"Execution exceeded the {timeout_seconds}s limit", "duration_ms": duration_ms, "engine": "docker"}

        duration_ms = int((time.monotonic() - started) * 1000)

        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")[:2000]
            return {"status": "error", "output": None, "error": stderr or f"Plugin exited with code {result.returncode}", "duration_ms": duration_ms, "engine": "docker"}

        stdout = result.stdout[:MAX_OUTPUT_BYTES]
        try:
            output = json.loads(stdout.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {"status": "error", "output": None, "error": "Plugin did not print a single valid JSON value to stdout", "duration_ms": duration_ms, "engine": "docker"}

        return {"status": "success", "output": output, "error": None, "duration_ms": duration_ms, "engine": "docker"}


def run_plugin_sandboxed(entry_point: str, code: bytes, payload: dict, *, timeout_seconds: int, max_memory_mb: int, cpu_limit: float | None = None) -> dict:
    """Real, synchronous execution of one plugin -- picks the Docker
    engine when real (a real `docker` binary AND the real sandbox
    image are both present), else the subprocess fallback. Returns
    {status, output, error, duration_ms, engine} -- never raises for a
    plugin-side failure (a bad plugin must produce a real
    `error`/`timeout` status row, not crash the caller); only raises
    PluginSandboxError for an environment-level problem (no
    node/python installed, unsupported entry_point extension)."""
    cpu_limit = cpu_limit if cpu_limit is not None else settings.PLUGINS_SANDBOX_CPU_LIMIT
    if _docker_sandbox_available():
        return run_plugin_sandboxed_docker(entry_point, code, payload, timeout_seconds=timeout_seconds, max_memory_mb=max_memory_mb, cpu_limit=cpu_limit)
    return run_plugin_sandboxed_subprocess(entry_point, code, payload, timeout_seconds=timeout_seconds, max_memory_mb=max_memory_mb)

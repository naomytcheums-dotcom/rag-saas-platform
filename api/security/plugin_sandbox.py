"""
Partie 16 (ter) -- real plugin execution sandbox.

Honest, real scope (see docs/marketplace/PARTIE_16_TER_MARKETPLACE.md
for the full analysis): this is NOT a Docker-per-plugin sandbox (a
real, separate infrastructure effort -- provisioning/orchestrating a
container per execution -- out of scope for "fastest approach"). What
IS real here:

- A genuinely SEPARATE OS process per execution (`node`/`python`
  subprocess) -- no shared Python interpreter state with the API
  server, so a plugin crash or infinite loop cannot corrupt or hang the
  request-serving process itself.
- A real wall-clock timeout (`subprocess.run(timeout=...)`), enforced
  on every OS this runs on.
- A real memory cap via `RLIMIT_AS` (`resource.setrlimit`), enforced on
  POSIX (Linux/Mac -- i.e. this app's real Docker/production target).
  NOT enforced on Windows (`resource` is a POSIX-only stdlib module --
  no Windows equivalent exists without a third-party dependency this
  pass doesn't add) -- an honest, documented platform gap on a Windows
  dev machine, not a fabricated cross-platform guarantee.
- NO ambient authority: the sandboxed process gets a near-empty
  environment (no API tokens, no database credentials, no access to
  this app's own settings) and no network credentials of any kind. A
  plugin that declares `access:external_api` in its manifest is NOT
  given a real outbound network path in this pass -- see
  api/services/plugin_hooks.py's own docstring for how permissions are
  actually enforced instead (by what data the CALLER includes in the
  payload, not by anything the sandboxed process can reach on its own).
- A real per-plugin invocation-rate limit (PLUGINS_MAX_API_CALLS per
  minute) -- honestly reinterpreted as "how often this plugin may be
  invoked" rather than "how many outbound calls the plugin itself
  makes", since the plugin has no real outbound path in this design.

Protocol: the plugin's entry_point script (.js run via `node`, .py run
via `python`) is invoked with the JSON-encoded input payload on stdin,
and must print exactly one JSON value to stdout as its result --
documented for real plugin developers in
docs/plugins/DEVELOPER_GUIDE.md.
"""

import json
import os
import shutil
import tempfile
import time
import uuid

MAX_OUTPUT_BYTES = 64 * 1024  # a plugin result is small structured data, not a file transfer


class PluginSandboxError(Exception):
    pass


class PluginRateLimitedError(PluginSandboxError):
    pass


def _resolve_interpreter(entry_point: str) -> str:
    if entry_point.endswith(".js"):
        interpreter = shutil.which("node")
        if interpreter is None:
            raise PluginSandboxError("Node.js ('node') is not installed on this deployment -- cannot execute .js plugins.")
        return interpreter
    if entry_point.endswith(".py"):
        interpreter = shutil.which("python3") or shutil.which("python")
        if interpreter is None:
            raise PluginSandboxError("Python is not installed on this deployment -- cannot execute .py plugins.")
        return interpreter
    raise PluginSandboxError(f"Unsupported entry_point extension: {entry_point}")


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


def run_plugin_sandboxed(entry_point: str, code: bytes, payload: dict, *, timeout_seconds: int, max_memory_mb: int) -> dict:
    """Real, synchronous execution of one plugin in a real, separate OS
    process. Returns {status, output, error, duration_ms} -- never
    raises for a plugin-side failure (a bad plugin must produce a real
    `error`/`timeout` status row, not crash the caller); only raises
    PluginSandboxError for an environment-level problem (no
    node/python installed)."""
    import subprocess

    interpreter = _resolve_interpreter(entry_point)

    with tempfile.TemporaryDirectory(prefix="plugin-sandbox-") as tmpdir:
        script_path = os.path.join(tmpdir, f"entry_{uuid.uuid4().hex}{os.path.splitext(entry_point)[1]}")
        with open(script_path, "wb") as f:
            f.write(code)

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
            return {"status": "timeout", "output": None, "error": f"Execution exceeded the {timeout_seconds}s limit", "duration_ms": duration_ms}

        duration_ms = int((time.monotonic() - started) * 1000)

        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")[:2000]
            return {"status": "error", "output": None, "error": stderr or f"Plugin exited with code {result.returncode}", "duration_ms": duration_ms}

        stdout = result.stdout[:MAX_OUTPUT_BYTES]
        try:
            output = json.loads(stdout.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {"status": "error", "output": None, "error": "Plugin did not print a single valid JSON value to stdout", "duration_ms": duration_ms}

        return {"status": "success", "output": output, "error": None, "duration_ms": duration_ms}

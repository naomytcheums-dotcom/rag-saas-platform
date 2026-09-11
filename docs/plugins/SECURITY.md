# Plugin security — real, honest scope

This is the document the "vision critique" questions below are
actually answered by. No claim here is aspirational — every mechanism
described is real code, verified live (`tests/test_plugin_sandbox.py`
spawns real `python`/`node` subprocesses, not mocks).

## Is the sandbox really isolated?

**Real, yes:**

- **A genuinely separate OS process per execution.** `api/security/plugin_sandbox.py`'s `run_plugin_sandboxed` shells out to `python`/`node` via `subprocess.run` — the plugin never runs inside the API server's own Python interpreter. A crash, infinite loop, or memory bomb in plugin code cannot corrupt or directly hang the process serving real HTTP requests.
- **A real wall-clock timeout.** `subprocess.run(timeout=PLUGINS_MAX_EXECUTION_TIME)` — enforced by the OS on every platform this runs on. Verified live: `test_execute_plugin_real_timeout` runs a plugin that sleeps 5s against a 1s limit and gets back a real `timeout` status in ~1s, not 5s.
- **No ambient authority.** The subprocess gets a near-empty environment (`{"PATH": ...}` only) — no API tokens, no database credentials, no access to this app's own `.env`/settings. Verified live: `test_execute_plugin_gets_no_ambient_environment` sets a real secret in the TEST process's own environment and confirms the sandboxed subprocess cannot see it.
- **Static gates before ANY code runs at all.** `api/security/plugin_manifest.py`'s `validate_manifest` (schema + a fixed permission/hook whitelist) and `scan_plugin_code` (regex-rejects `eval`, `new Function`, `exec`, `os.system`, `subprocess`, Node `child_process`/`fs`) both run at publish time, before a byte of code is even stored.

**Real, honest limits — not fabricated:**

- **Memory cap is POSIX-only.** `RLIMIT_AS` (`resource.setrlimit`) is a Linux/Mac-only stdlib mechanism — it is NOT enforced on Windows (this app's real Docker/production target is Linux, where it works; a Windows dev machine gets no memory enforcement, and that gap is not hidden here).
- **Not container-per-plugin.** This is process isolation, not Docker/VM/gVisor isolation. A determined, malicious plugin author with a novel Python/Node interpreter exploit could still escape a subprocess sandbox in ways a real container boundary would stop. A genuine container-per-execution sandbox is real, separate infrastructure work this pass does not build — see "What's explicitly NOT built" below.
- **The static scan is real but simple regex matching**, the same class of tool as this project's own `api/services/security_scan.py` secret scanner — not a full taint-analysis or AST-based tool. It catches the obvious, common escape attempts (`eval`, shelling out) by name; it does not catch every conceivable obfuscated attempt (e.g. `getattr(__builtins__, "e" + "val")`). Two Celery jobs (below) provide a second, later pass, but this is still pattern matching, not a proof of safety.
- **`access:external_api` grants nothing real.** A plugin can declare this permission, but the sandboxed process has no real outbound network credentials in this pass — declaring it is honest bookkeeping for a future capability, not a currently-enforced grant.

## What's explicitly NOT built (said plainly, not left implicit)

- A real container-per-execution sandbox (Docker/gVisor/Firecracker).
- Real outbound network access for `access:external_api` plugins.
- Automatic firing of 6 of the 7 hooks from their own real platform events (only `on_document_uploaded` is wired — see `docs/plugins/DEVELOPER_GUIDE.md`'s hook table).
- Any actual enforcement that a plugin only reads/writes what its declared `permissions` say — enforcement today is entirely upstream, in what `api/services/plugin_hooks.py`'s `trigger_hook` chooses to put into the payload. A plugin invoked manually via `POST .../execute` with a hand-crafted payload receives exactly what the caller sent, regardless of its declared permissions — permissions are not yet checked against the actual payload contents at execution time.

## Automated re-scanning (Celery, `api/tasks/plugins.py`)

- `validate_pending_plugins` (hourly) — re-runs the static scan against every `pending` plugin's stored code; auto-`reject`s on a new match (a scan rule added/tightened after submission, before review).
- `scan_plugin_security` (daily) — same re-scan against every `approved` plugin; auto-`suspend`s on a new match (catches an already-live plugin, not just new submissions). Existing installations are left in place — see `docs/plugins/MARKETPLACE.md`'s own note on `suspend`.

## Does execution really respect PLUGINS_SANDBOX_ENABLED / PLUGINS_ENABLED?

Yes, and both fail closed, not open: `PLUGINS_ENABLED=False` returns a
real `503` before anything runs. `PLUGINS_SANDBOX_ENABLED=False`
never falls back to running the code unsandboxed — it records a real
`error` execution explaining exactly why, verified live in
`test_execute_plugin_honestly_refuses_when_sandbox_disabled`.

## Rate limiting

`PLUGINS_MAX_API_CALLS` (default 100/minute) is enforced per-plugin,
counted from real `PluginExecution` rows in the last 60 seconds —
honestly scoped to "how often this plugin may be invoked", not "how
many outbound calls the plugin itself makes" (there is no real
outbound path for it to make calls on, see above).
